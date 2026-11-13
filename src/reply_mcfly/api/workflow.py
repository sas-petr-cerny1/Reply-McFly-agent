import base64
import binascii
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from reply_mcfly.adapters.cloud_tasks_adapter import CloudTasksAdapter
from reply_mcfly.adapters.gemini_adapter import GeminiAdapter
from reply_mcfly.adapters.gmail_adapter import GmailAdapter
from reply_mcfly.adapters.google_clients import GmailServiceFactory
from reply_mcfly.adapters.oidc_adapter import GoogleOidcVerifier
from reply_mcfly.adapters.postgres_adapter import PostgresEmailRepository
from reply_mcfly.adapters.rag_factory import build_rag
from reply_mcfly.adapters.web_factory import build_web_search
from reply_mcfly.application.attachment_service import AttachmentService
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.gmail_sync_service import GmailSyncService
from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.application.telemetry import emit
from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.email import Status, WorkflowError, require_mailbox
from reply_mcfly.domain.grounding import LiteralReplyValidator
from reply_mcfly.domain.sender_policy import SenderConfigurationError, parse_sender_policy
from reply_mcfly.ports.email import TaskQueuePort


class IdentityVerifier(Protocol):
    def verify(self, token: str) -> None: ...


@dataclass(frozen=True)
class IngressServices:
    mailbox_id: str
    queue: TaskQueuePort
    verifier: IdentityVerifier


@dataclass(frozen=True)
class WorkerServices:
    mailbox_id: str
    sync: GmailSyncService
    processing: EmailProcessingService
    verifier: IdentityVerifier


type WorkflowServices = IngressServices | WorkerServices


def build_services(
    settings: Settings, engine: Engine | None, service_name: str
) -> WorkflowServices:
    if not all(
        (
            settings.mailbox_id,
            settings.sync_queue,
            settings.worker_url,
            settings.tasks_service_account,
        )
    ):
        raise WorkflowError("WORKFLOW_NOT_CONFIGURED", status=503)
    mailbox = settings.mailbox_id.casefold()
    queue = CloudTasksAdapter(
        settings.gcp_project_id,
        settings.gcp_region,
        settings.sync_queue,
        settings.process_queue,
        settings.worker_url,
        settings.tasks_service_account,
    )
    if service_name == "ingress":
        if not settings.ingress_audience or not settings.pubsub_service_account:
            raise WorkflowError("WORKFLOW_NOT_CONFIGURED", status=503)
        return IngressServices(
            mailbox,
            queue,
            GoogleOidcVerifier(settings.ingress_audience, settings.pubsub_service_account),
        )
    if engine is None or not all(
        (settings.allowed_senders, settings.gmail_oauth_secret_version, settings.process_queue)
    ):
        raise WorkflowError("WORKFLOW_NOT_CONFIGURED", status=503)
    try:
        sender_policy = parse_sender_policy(settings.allowed_senders, settings.mailbox_id)
    except SenderConfigurationError:
        raise WorkflowError("INVALID_RECIPIENT_CONFIGURATION", status=503) from None
    gmail = GmailAdapter(GmailServiceFactory(settings.gmail_oauth_secret_version), mailbox)
    repository = PostgresEmailRepository(engine)
    gemini = GeminiAdapter(
        settings.gcp_project_id, settings.vertex_ai_location, settings.gemini_model
    )
    rag = build_rag(settings, engine)
    web = build_web_search(settings)
    verifier = GoogleOidcVerifier(settings.worker_url.rstrip("/"), settings.tasks_service_account)
    return WorkerServices(
        mailbox,
        GmailSyncService(repository, gmail, queue, maintenance=gmail),
        EmailProcessingService(
            repository,
            gmail,
            gemini,
            mailbox,
            ReplyService(sender_policy, FallbackTemplates(), LiteralReplyValidator()),
            AttachmentService(gemini),
            rag=rag.provider,
            enable_rag=settings.enable_rag,
            rag_query_builder=rag.query_builder,
            rag_timeout=rag.timeout,
            web=web.provider,
            enable_web_search=settings.enable_web_search,
            web_query_builder=web.query_builder,
            web_timeout=web.timeout,
            sender_daily_reply_limit=settings.sender_daily_reply_limit,
        ),
        verifier,
    )


class PushMessage(BaseModel):
    data: str = Field(max_length=12000)
    messageId: str = Field(min_length=1, max_length=255)


class PushEnvelope(BaseModel):
    message: PushMessage


class GmailNotification(BaseModel):
    emailAddress: str = Field(min_length=3, max_length=320)
    historyId: str = Field(pattern=r"^\d+$", max_length=32)

    @field_validator("historyId", mode="before")
    @classmethod
    def normalize_history_id(cls, value: object) -> object:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return str(value)
        return value


class SyncTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mailbox_id: str = Field(min_length=3, max_length=320)


class ProcessTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: UUID


async def read_body[T: BaseModel](request: Request, model: type[T]) -> T:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise WorkflowError("REQUEST_TOO_LARGE", status=413)
    try:
        return model.model_validate_json(bytes(body))
    except ValidationError:
        raise WorkflowError("INVALID_REQUEST") from None


def install_workflow_routes(
    app: FastAPI, service_name: str, provider: Callable[[], WorkflowServices]
) -> None:
    @app.exception_handler(WorkflowError)
    async def workflow_error(request: Request, error: WorkflowError) -> JSONResponse:
        # The same id goes to the caller and to the log, so a reported failure can be found.
        correlation_id = str(uuid4())
        emit(
            "request_failed",
            status=str(error.status),
            error_code=error.code,
            correlation_id=correlation_id,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=error.status,
            content={
                "error": {
                    "code": error.code,
                    "message": "Request could not be completed",
                    "retryable": error.retryable,
                    "correlation_id": correlation_id,
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return await workflow_error(
            request, WorkflowError("DATABASE_UNAVAILABLE", retryable=True, status=503)
        )

    async def authorize(request: Request) -> WorkflowServices:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:] or len(header) > 8192:
            raise WorkflowError("UNAUTHORIZED", status=401)
        services = provider()
        await run_in_threadpool(services.verifier.verify, header[7:])
        return services

    if service_name == "ingress":

        @app.post("/events/gmail", status_code=204)
        async def gmail_event(request: Request) -> Response:
            services = await authorize(request)
            if not isinstance(services, IngressServices):
                raise WorkflowError("INVALID_SERVICE_CONFIGURATION", status=503)
            envelope = await read_body(request, PushEnvelope)
            try:
                raw = base64.b64decode(envelope.message.data, validate=True)
                notification = GmailNotification.model_validate_json(raw)
            except (ValueError, binascii.Error, ValidationError):
                raise WorkflowError("INVALID_REQUEST") from None
            require_mailbox(notification.emailAddress, services.mailbox_id)
            await run_in_threadpool(
                services.queue.sync, services.mailbox_id, envelope.message.messageId
            )
            return Response(status_code=204)
    else:

        @app.post("/tasks/sync")
        async def sync_task(request: Request) -> dict[str, int]:
            services = await authorize(request)
            if not isinstance(services, WorkerServices):
                raise WorkflowError("INVALID_SERVICE_CONFIGURATION", status=503)
            task = await read_body(request, SyncTask)
            require_mailbox(task.mailbox_id, services.mailbox_id)
            count = await run_in_threadpool(services.sync.sync, services.mailbox_id)
            return {"discovered": count}

        @app.post("/tasks/process")
        async def process_task(request: Request) -> dict[str, str]:
            services = await authorize(request)
            if not isinstance(services, WorkerServices):
                raise WorkflowError("INVALID_SERVICE_CONFIGURATION", status=503)
            task = await read_body(request, ProcessTask)
            status = await run_in_threadpool(services.processing.process, task.job_id)
            if status == Status.DELIVERY_UNKNOWN:
                # Redelivery verifies Gmail Sent; it does not repeat Gmail Send.
                raise WorkflowError("DELIVERY_UNKNOWN", retryable=True, status=503)
            return {"status": status.value}
