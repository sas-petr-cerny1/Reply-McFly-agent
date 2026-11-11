# Reply McFly agent — Kompletní technický blueprint

### Schválená upřesnění prvního textového slice — 11. 11. 2026

Zdroj: výslovná rozhodnutí vlastníka v chatu. Tato upřesnění mají přednost před
staršími pracovními předpoklady, aniž by schvalovala zbývající formulářové blockery.

- Příjemce určuje backend z původního From a explicitního allowlistu testovacích odesílatelů.
  Reply-To se ignoruje; vlastní a rozpoznané automatické zprávy se neodesílají.
  From není důkaz identity. Zachovává se původní Gmail threadId a reply hlavičky.
- Deterministické šablony FALLBACK_MISSING_INFORMATION a FALLBACK_UNSUPPORTED_ATTACHMENT
  byly schváleny přesně. Jediné implementované znění je v
  src/reply_mcfly/domain/reply_templates.py a chrání je golden testy.
  SENT odpověď eviduje response_type=FALLBACK a fallback_reason.
- Bezpečnostní riziko, nejednoznačnost nebo neověřitelný výstup vede do REVIEW_REQUIRED
  bez odeslání. DELIVERY_UNKNOWN se řeší dohledáním Sent, nikoliv automatickým fallbackem
  či opakováním sendu. Zpráva smí způsobit maximálně jednu automatickou odpověď.
- První GENERATED čerpá jen aktuální e-mail. Výstup obsahuje response_type,
  proposed_reply, evidence se source_id a exact_quote, missing_information a requires_review.
  Backend nezávisle ověřuje zdroje a doslovné pasáže; dovolí jen kontrolovatelné
  citace s připsáním odesílateli, nikoliv volné parafráze a nové ceny, termíny či fakta.
  Přítomnost citace ani LLM hodnocení nejsou důkaz skutečné pravdivosti.
- Finální PoC musí obsahovat Conversation History, RAG i Live Web Search.
  První textový inkrement je neaktivuje; rozhraní jsou připravená.
- Schválené návrhové hodnoty: projekt reply-mcfly-poc, region europe-west1,
  Vertex AI location eu, model gemini-3.5-flash. Přechod na global vyžaduje samostatné schválení.
- Existující gmail-events topic, servisní účty a sync-queue/process-queue se nevytvářejí znovu.
  Aktuální inventura, IAM návrh, oddělené Cloud Shell kroky a cenové předpoklady
  jsou v docs/operations/GCP_CLOUD_SHELL.md, se zdrojem inventury od vlastníka z Cloud Shellu.
- Aktuální autorizovaný krok: dokončit lokální Docker workflow, doložit skutečné kontroly
  a připravit Cloud Shell příkazy a odhad nákladů. IAM ani placené prostředky neměnit.
  Monitoring budget 20 USD není svolení k utrácení ani globální limit nákladů.
- Skutečný Gmail/GCP E2E a latence pod 120 s zůstávají NESPLNĚNÉ.
  Dedikovaná schránka, allowlist a OAuth zatím nebyly potvrzené; skutečný send není povolený.


> PRACOVNÍ NÁVRH. Nepotvrzené odpovědi nesmí být považované za schválený požadavek. Formulář není production gate.

## Stav

- Povinné položky: 14/124
- Blockery: 110
- Formální vývojový gate: blokováno
- Formální produkční gate: blokováno

## 00 · Projektový profil a původ

*Cíl:* Nejdřív zjisti, co vlastně stavíš, kdo rozhoduje a které volitelné kapitoly se týkají projektu.

*Gate:* Existuje pojmenovaný cíl, vlastník, zdroj a rozlišení faktů od předpokladů.

### Jak se aplikace jmenuje?

- ID: project_name (povinné)
- Stav: **NETÝKÁ SE**
- Vlastník: Petr Černý
- Zdroj / důkaz: Jsem ownrem use-casu

Reply McFly agent

### Jaký typ řešení stavíš?

- ID: project_type (povinné)
- Stav: **POTVRZENO**
- Vlastník: Alza
- Zdroj / důkaz: Jedná se o Email agenta

other

### Kdo odpovídá za produkt a schvaluje scope?

- ID: project_owner (povinné)
- Stav: **POTVRZENO**
- Vlastník: Iveta Pajerová
- Zdroj / důkaz: Je to use-case zadání

HR pracovnice

### Z čeho vychází zadání?

- ID: source_assignment (povinné)
- Stav: **POTVRZENO**
- Vlastník: Alza
- Zdroj / důkaz: PDF zadání use-casu

Jedná se o use-case od alzy

### Jaký konkrétní problém řešíš?

- ID: problem (povinné)
- Stav: **POTVRZENO**
- Vlastník: Alza
- Zdroj / důkaz: viz pdf zadání

Příchozí zákaznické e-maily vyžadují ruční čtení, zpracování příloh, vyhledávání relevantních informací a sestavení odpovědi. Tento postup zabírá čas, zpomaluje reakce a při větším počtu zpráv vytváří riziko přehlédnutí důležitých informací.

Cílem je automaticky zpracovat nové e-maily včetně textových, obrazových a zvukových příloh, dohledat relevantní informace v dostupných dokumentech a odeslat věcně správnou odpověď ve stejném e-mailovém vlákně, ideálně do 120 sekund od přijetí zprávy.

Úspěch bude ověřen praktickým testem: nová zpráva bude zpracována bez ručního zásahu, odpověď bude vycházet z relevantních zdrojů a opakované doručení stejné události nezpůsobí duplicitní odpověď.

### Jakou změnu má uživatel po nasazení zaznamenat?

- ID: outcome (povinné)
- Stav: **POTVRZENO**
- Vlastník: Alza
- Zdroj / důkaz: use-case description

Uživatel po nasazení zaznamená, že nové příchozí e-maily jsou automaticky zpracovány bez nutnosti ručního zásahu. AI agent přečte obsah zprávy včetně podporovaných příloh, vyhledá relevantní informace v dostupných dokumentech a odešle odpověď přímo do původního e-mailového vlákna.

Očekávaný výsledek: Zákazník obdrží relevantní odpověď do 120 sekund od přijetí e-mailu v testovaných scénářích. Obsluha schránky nemusí každou zprávu ručně číst, dohledávat informace ani sestavovat odpověď. Pokud agent nemá dostatek podkladů, nevymýšlí si informace a zvolí definovaný náhradní postup.

### Jaká fakta jsou potvrzená a kým?

- ID: confirmed_facts (povinné)
- Stav: **POTVRZENO**

**Potvrzená fakta ze zadání Alzy:**

- **Zadavatel – Alza:** Požaduje vytvořit AI agenta, který automaticky zpracovává nově příchozí e-maily v Gmailu / Google Workspace.
- **Zadavatel – Alza:** Agent musí umět zpracovat text e-mailu a přílohy ve formátech PDF, MP3, WAV, JPEG a PNG.
- **Zadavatel – Alza:** Agent má pomocí jazykového modelu vytvořit relevantní odpověď a odeslat ji do původního e-mailového vlákna.
- **Zadavatel – Alza:** Cílová doba zpracování a odpovědi je do 120 sekund od přijetí zprávy.
- **Zadavatel – Alza:** Součástí řešení musí být alespoň jedna pokročilá funkce: RAG, Conversation Awareness nebo Web Search.
- **Zadavatel – Alza:** Aplikace má být nasazena do veřejného cloudu, preferovaně Google Cloud Platform.

**Návrhová rozhodnutí – zatím nepotvrzená zadavatelem:**

- Jako pokročilou funkci implementovat RAG nad dokumenty o fiktivním produktu.
- Použít Python, FastAPI, Docker, Cloud Run, Firestore a Gemini.
- Oddělit příjem událostí od zpracování e-mailů.
- Navrhnout modulární architekturu umožňující budoucí rozšíření.

**Dosud neověřeno:** Skutečná doba odpovědi, kvalita generovaných odpovědí, správnost vyhledávání v dokumentech a odolnost proti duplicitnímu zpracování. Tyto vlastnosti musí potvrdit implementace a testy.

### Co zatím nevíš a kdo to rozhodne?

- ID: initial_unknowns (povinné)
- Stav: **POTVRZENO**

**OTEVŘENÉ OTÁZKY – ALZA AI EMAIL AGENT**

**1. Testovací e-mailová schránka**
- Otázka: Použijeme osobní Gmail, nebo Google Workspace?
- Rozhoduje: Vývojář / Alza

**2. AI model a cloudové služby**
- Otázka: Který model Gemini bude dostupný v rámci GCP Free Trial a jaké budou jeho limity?
- Rozhoduje: Vývojář

**3. Pokročilá funkce (Advanced Feature)**
- Otázka: Potvrdíme RAG jako jedinou požadovanou pokročilou funkci?
- Rozhoduje: Vývojář

**4. Znalostní dokumenty**
- Otázka: Jaké 1–3 dokumenty použijeme pro RAG a jak ověříme správnost vyhledávání?
- Rozhoduje: Vývojář

**5. Databáze**
- Otázka: Podporuje dostupná konfigurace Firestore požadované vektorové vyhledávání v rámci rozpočtu?
- Rozhoduje: Vývojář

**6. Chování při neúplných informacích**
- Otázka: Co má agent udělat, pokud nenajde odpověď, nerozumí dotazu nebo nedokáže zpracovat přílohu?
- Rozhoduje: Vývojář / případně Alza

**7. Bezpečnost a duplicity**
- Otázka: Jak zabráníme nepovolenému odesílání, prompt injection a opakovanému zpracování stejného e-mailu?
- Rozhoduje: Vývojář

**8. Výkon a časový limit**
- Otázka: Dokáže systém automaticky zpracovat zprávu a odeslat odpověď do 120 sekund?
- Rozhoduje: Vývojář na základě testování

**9. Akceptační testy**
- Otázka: Jak prokážeme funkčnost zpracování příloh, kvalitu RAG, správnost odpovědí a bezpečnost?
- Rozhoduje: Vývojář

**PRIORITY**

**P0 – Vyřešit před implementací**
- Výběr testovacího Gmail účtu.
- Ověření dostupnosti Gemini a GCP služeb.
- Potvrzení RAG jako pokročilé funkce.
- Výběr znalostních dokumentů.
- Rozhodnutí o databázi.

**P1 – Vyřešit během implementace**
- Chování při chybách a nedostatku informací.
- Bezpečnost a prevence duplicit.
- Výkonnostní a akceptační testy.

**POZNÁMKA**

Technická rozhodnutí přijímá vývojář, pokud zadání Alzy neurčuje jinak. Neověřené předpoklady musí být potvrzeny před jejich implementací.

### Používáš AI/LLM/ML v produkčním flow?

- ID: uses_ai (povinné)
- Stav: **POTVRZENO**
- Vlastník: Alza
- Zdroj / důkaz: Jedná se o agenta

ano

### Pracuje aplikace s platbami nebo předplatným?

- ID: payments (povinné)
- Stav: **POTVRZENO**
- Vlastník: Alza
- Zdroj / důkaz: zadání

ne

### Nahrává nebo ukládá aplikace uživatelské soubory?

- ID: has_files (povinné)
- Stav: **POTVRZENO**
- POZOR: CHYBÍ DŮKAZ

ano

### Má více organizací/tenantů sdílet aplikaci?

- ID: multitenant (povinné)
- Stav: **PŘEDPOKLAD**

ne

### Potřebuješ realtime, websockety, push nebo streaming?

- ID: realtime (povinné)
- Stav: **POTVRZENO**
- POZOR: CHYBÍ DŮKAZ

ano

### Budeš zpracovávat osobní či jiné citlivé údaje?

- ID: personal_data (povinné)
- Stav: **POTVRZENO**
- POZOR: CHYBÍ DŮKAZ

ano

### Budeš volat externí služby/API?

- ID: integrations_flag (povinné)
- Stav: **POTVRZENO**
- POZOR: CHYBÍ DŮKAZ

ano

### Jde o nový produkt, nebo existující codebase?

- ID: existing_repo (doplňkové)
- Stav: **POTVRZENO**

Jedná se o nový produkt

## 01 · Produkt a strategické zadání

*Cíl:* Vymez hodnotu, MVP, uživatele, priority a měřitelný úspěch.

*Gate:* MVP lze vysvětlit, ověřit a má vlastníka i metriky.

### Kdo je primární uživatel a jaké má potřeby?

- ID: primary_user (povinné)
- Stav: **PŘEDPOKLAD**
- Vlastník: Vývojář
- Zdroj / důkaz: můj návrh

**1. Primární uživatel – Pracovník zákaznické podpory**

Potřebuje automaticky zpracovávat příchozí e-maily a přílohy, vyhledávat relevantní informace a odesílat správné odpovědi bez ručního zásahu.

**2. Sekundární uživatel – Zákazník**

Odesílá dotazy na produkty, reklamace nebo vrácení zboží. Potřebuje získat rychlou, přesnou a srozumitelnou odpověď ve stejném e-mailovém vlákně.

**3. Technický uživatel – Správce aplikace**

Potřebuje konfigurovat integrace, spravovat znalostní dokumenty, sledovat zpracování e-mailů a řešit chyby systému.

### Jak poznáš, že produkt řeší problém?

- ID: success_definition (povinné)
- Stav: **PŘEDPOKLAD**

Úspěch produktu bude ověřen během závěrečného pilotního testování (UAT) podle následujících kritérií:

1. **Automatizace:** 100 % podporovaných testovacích e-mailů se zpracuje bez ručního spuštění.
2. **Rychlost:** Alespoň 95 % testovacích e-mailů obdrží odpověď do 120 sekund od přijetí.
3. **Přílohy:** Úspěšné zpracování všech požadovaných formátů (PDF, MP3, WAV, JPEG, PNG).
4. **Kvalita odpovědí:** Alespoň 90 % odpovědí je věcně správných a relevantních podle předem připravených testovacích scénářů.
5. **RAG:** Agent dohledá správné informace ve znalostních dokumentech a nevymýšlí odpovědi při nedostatku podkladů.
6. **Spolehlivost:** Žádné duplicitní odpovědi ani odeslání neoprávněnému příjemci během testování.

**Způsob měření:** Automatizované integrační a end-to-end testy, kontrola odeslaných e-mailů, měření doby zpracování a porovnání odpovědí s referenčními výsledky.
**Časový horizont:** Závěrečné UAT po nasazení PoC do Google Cloud Platform.
**Poznámka:** Uvedené procentuální cíle jsou navržená akceptační kritéria. Zadáním je stanoven zejména požadavek na odpověď do 120 sekund.

### Co přesně patří do MVP?

- ID: mvp_scope (povinné)
- Stav: **POTVRZENO**
- POZOR: CHYBÍ DŮKAZ

**Do MVP patří:**

1. **Automatický příjem e-mailů** – detekce nových zpráv v Gmailu bez ručního spuštění.
2. **Zpracování obsahu a příloh** – čtení textu e-mailu a příloh PDF, MP3, WAV, JPEG a PNG.
3. **RAG vyhledávání** – načtení 1–3 znalostních dokumentů, jejich indexace a vyhledání relevantních informací.
4. **Generování odpovědí** – vytvoření věcně správné odpovědi pomocí Gemini na základě e-mailu, příloh a nalezených informací.
5. **Automatické odesílání** – odeslání odpovědi do původního e-mailového vlákna s cílovou dobou do 120 sekund.
6. **Spolehlivost a bezpečnost** – prevence duplicit, ošetření chyb, bezpečná správa přístupových údajů a kontrola odesílání.
7. **Cloudové nasazení** – kontejnerizovaná aplikace v Dockeru nasazená na Google Cloud Run.
8. **Ověření funkčnosti** – end-to-end testy příjmu, příloh, RAG, generování odpovědi a odesílání.

**Mimo MVP:** Webové uživatelské rozhraní, multitenancy, MCP integrace, autonomní sandbox, pokročilá analytika a samostatná správa více AI agentů.

### Co do první verze záměrně nepatří?

- ID: out_of_scope (povinné)
- Stav: **PŘEDPOKLAD**

**Do první verze (MVP) záměrně nepatří:**

- Webové uživatelské a administrační rozhraní.
- Podpora více organizací a e-mailových schránek (multitenancy).
- Pokročilé funkce Conversation Awareness a Web Search – implementován bude pouze RAG.
- Integrace s ERP, CRM, objednávkovými a platebními systémy.
- MCP servery, autonomní agentní nástroje a samostatný sandbox.
- Vlastní provoz PostgreSQL nebo Milvus.
- Automatické učení z historie zákaznických konverzací.
- Pokročilá analytika, reporting a dashboardy.
- Správa více AI agentů a jejich vzájemná koordinace.
- Produkční vysoká dostupnost, garantované SLA a rozsáhlé zátěžové testování.

**Důvod:** První verze se zaměřuje na ověření automatického zpracování e-mailů, příloh, RAG vyhledávání a odesílání odpovědí v cloudu. Architektura umožní pozdější rozšíření bez zásadního přepracování hlavního workflow.

### Proč bude uživatel aplikaci používat?

- ID: value_proposition (povinné)
- Stav: **PŘEDPOKLAD**
- Vlastník: Alza
- Zdroj / důkaz: Zadání od alzy

Pracovník zákaznické podpory bude aplikaci využívat, protože automatizuje čtení e-mailů, zpracování příloh, vyhledávání informací a tvorbu odpovědí. Tím snižuje množství rutinní práce a umožňuje věnovat se složitějším požadavkům.

Zákazník získá rychlou, srozumitelnou a relevantní odpověď ve stejném e-mailovém vlákně, s cílovou dobou do 120 sekund.

Správce aplikace získá systém, jehož provoz lze monitorovat, chyby diagnostikovat a znalostní dokumenty či integrace průběžně aktualizovat.

### Jak jsi ověřil problém a potřebu?

- ID: user_research (povinné)
- Stav: **POTVRZENO**

Problém a potřeba byly identifikovány na základě analýzy zadání Alzy, které požaduje automatické zpracování příchozích e-mailů, příloh a generování odpovědí do 120 sekund.

Přímé rozhovory s uživateli ani analýza reálných provozních dat zatím neproběhly.

Potřeba bude technicky ověřena prostřednictvím funkčního PoC a end-to-end testů, které prověří automatizaci, správnost odpovědí, relevanci RAG vyhledávání a dobu zpracování. Uživatelská potřebnost tím však nebude samostatně potvrzena.

### Jak bude produkt financovaný / udržitelný?

- ID: business_model (povinné)
- Stav: **POTVRZENO**

Produkt bude v rámci PoC financován z dostupného kreditu Google Cloud Free Trial a bezplatných kvót cloudových služeb. Není určen ke komerčnímu prodeji.

**Provozní náklady:**
- Cloud Run – provoz aplikačních kontejnerů.
- Firestore – ukládání stavu a RAG dat.
- Gemini / Vertex AI – generování odpovědí a embeddingů.
- Pub/Sub a Cloud Tasks – automatické zpracování e-mailů.

**Interní hodnota:**
- Snížení ruční práce zákaznické podpory.
- Rychlejší vyřizování zákaznických dotazů.
- Možnost rozšíření bez zásadního přepracování aplikace.

**Udržitelnost:** Náklady budou záviset na počtu zpracovaných e-mailů, velikosti příloh, spotřebě AI modelů a cloudových prostředků. Před produkčním provozem bude nutné ověřit náklady na jednu zprávu a ekonomickou návratnost.

**Omezení:** Free Trial je časově omezený. Po jeho skončení bude provoz vyžadovat plac

### Jaká jsou časová, smluvní a organizační omezení?

- ID: business_constraints (povinné)
- Stav: **POTVRZENO**

Do Středy 11/11/2026 poslat na github a i s prezentací

### Kdo další schvaluje bezpečnost, data, finance a go-live?

- ID: stakeholders (doplňkové)
- Stav: **POTVRZENO**

V rámci PoC odpovídá za technické řešení, základní zabezpečení, náklady a nasazení vývojář aplikace.

Při případném produkčním nasazení by bylo nutné schválení následujících rolí:

- **Bezpečnost:** IT Security – přístupová oprávnění, integrace a zabezpečení aplikace.
- **Osobní údaje:** DPO / právní oddělení – GDPR a zpracování zákaznických dat.
- **Finance:** Vlastník rozpočtu – provozní náklady cloudových služeb.
- **Go-live:** Produktový nebo business vlastník – schválení funkčnosti a uvedení do provozu.

Konkrétní schvalovatelé ze strany Alzy nejsou v zadání určeni. Produkční nasazení není součástí aktuálního PoC.

### Jaké jsou alternativy a proč je řešení lepší?

- ID: competitors (doplňkové)
- Stav: **POTVRZENO**

**Alternativní řešení:**

1. **Ruční zákaznická podpora** – pracovníci čtou e-maily, zpracovávají přílohy a ručně odpovídají. Nevýhodou je časová náročnost a omezená kapacita.
2. **Pravidla a šablony v Gmailu** – automatizují jednoduché odpovědi, ale nedokážou spolehlivě řešit složitější dotazy a analyzovat přílohy.
3. **Hotové platformy (Zendesk, Intercom)** – nabízejí automatizaci zákaznické podpory, ale mohou vyžadovat placené licence a přizpůsobení.
4. **Jednoduchý LLM bez RAG** – generuje odpovědi, ale nemá zajištěný přístup k aktuálním interním znalostním dokumentům.

**Výhody navrženého řešení:**

- Automatické zpracování e-mailů a multimodálních příloh.
- RAG umožňuje odpovídat na základě konkrétních znalostních dokumentů.
- Cílová doba odpovědi do 120 sekund.
- Kontrola nad workflow, daty a integracemi.
- Modulární architektura umožňující budoucí rozšíření.
- Nízké počáteční infrastrukturní náklady při malém PoC.

**Hlavní přínos:** Řešení kombinuje automatizaci e-mailové komunikace, analýzu příloh a vyhledávání ve znalostních dokumentech v jedné rozšiřitelné aplikaci. Jeho skutečná výhodnost oproti hotovým produktům musí být ověřena testováním a porovnáním nákladů.

### Jaká jedna metrika nejlépe reprezentuje hodnotu?

- ID: north_star (doplňkové)
- Stav: **POTVRZENO**

**North Star metrika:** Podíl příchozích e-mailů, které AI agent automaticky a správně vyřídí do 120 sekund bez lidského zásahu.

**Výpočet:** (Počet správně vyřízených e-mailů do 120 sekund / Celkový počet podporovaných příchozích e-mailů) × 100.

**Cíl PoC:** Alespoň 90 % úspěšně vyřízených testovacích e-mailů.

**Měření:** End-to-end testy, kontrola správnosti odpovědí a časových záznamů zpracování.

### Jaké produktové události budeš měřit a se souhlasem koho?

- ID: analytics_events (doplňkové)
- Stav: **PŘEDPOKLAD**

**Měřené produktové události:**

- `email_received` – přijetí nového e-mailu.
- `email_processing_started` – zahájení zpracování.
- `attachment_processed` – úspěšné zpracování přílohy.
- `rag_retrieval_completed` – dokončení vyhledávání relevantních informací.
- `response_generated` – vygenerování odpovědi.
- `email_reply_sent` – úspěšné odeslání odpovědi.
- `email_processing_failed` – chyba při zpracování.
- `email_requires_review` – zpráva vyžadující ruční kontrolu.
- `duplicate_email_skipped` – přeskočení již zpracované zprávy.

**Sledované metriky:**
- Doba zpracování e-mailu.
- Podíl správně vyřízených e-mailů do 120 sekund.
- Úspěšnost a chybovost zpracování.
- Počet duplicitních událostí.
- Spotřeba tokenů a odhad nákladů na AI.

**Souhlas a ochrana dat:**

Pro PoC budou použita syntetická testovací data. Provozní metriky budou zaznamenávány bez obsahu e-mailů, příloh a osobních údajů.

Měření technických událostí v testovacím prostředí schvaluje vývojář. Případné měření se skutečnými zákaznickými údaji musí předem posoudit a schválit správce osobních údajů ve spolupráci s DPO podle příslušného právního základu.

## 02 · UX, role a user journey

*Cíl:* Popiš akci člověka i všechny smysluplné alternativy.

*Gate:* U každého klíčového flow existuje happy path, chyba a výsledek.

### Jaké role a oprávnění má aplikace?

- ID: actor_roles (povinné)
- Stav: **PŘEDPOKLAD**

**Role a oprávnění aplikace:**

**1. Zákazník**
- Odesílá e-mailové dotazy a přílohy.
- Přijímá automatické odpovědi.
- Nemá přístup do aplikace ani k jejím interním datům.

**2. Pracovník zákaznické podpory**
- Přistupuje k zákaznické e-mailové schránce podle oprávnění v Gmailu.
- Kontroluje odpovědi a řeší požadavky, které agent nedokáže vyřídit.
- Nemá automaticky administrátorská oprávnění.

**3. Správce aplikace**
- Spravuje konfiguraci, integrace a znalostní dokumenty.
- Monitoruje provoz a řeší chyby.
- Spravuje přístupová oprávnění prostřednictvím Google Cloud IAM.

**4. AI agent (systémová identita)**
- Čte zprávy a přílohy z autorizované schránky.
- Vyhledává informace pomocí RAG.
- Generuje a odesílá odpovědi.
- Má pouze nezbytná oprávnění k externím službám.

**Zdroj pravdy pro oprávnění:**
- Google Cloud IAM – oprávnění cloudových služeb.
- Gmail OAuth 2.0 – autorizace přístupu ke schránce.
- Aplikační pravidla – povolené operace AI agenta.

**MVP:** Neobsahuje vlastní uživatelské účty ani RBAC. Přístup je řízen externími systémy.

### Co spustí hlavní use case a odkud uživatel přichází?

- ID: entry_trigger (povinné)
- Stav: **POTVRZENO**

**Spouštěč hlavního use casu:** Přijetí nového e-mailu do autorizované Gmail / Google Workspace schránky.

**Odkud uživatel přichází:** Zákazník odešle e-mail ze svého e-mailového klienta na adresu zákaznické podpory. Do aplikace se nepřihlašuje.

**Průběh spuštění:**
1. Gmail zaznamená příchozí zprávu.
2. Gmail Watch odešle oznámení prostřednictvím Google Pub/Sub.
3. Cloud Run Ingress přijme událost a vytvoří úlohu v Cloud Tasks.
4. Worker načte novou zprávu a automaticky zahájí zpracování.

**Výsledek:** AI agent zpracuje e-mail a přílohy, vyhledá relevantní informace pomocí RAG a odešle odpověď do původního e-mailového vlákna.

### Jaké vstupy uživatel poskytuje?

- ID: user_inputs (povinné)
- Stav: **PŘEDPOKLAD**

**Vstupy poskytované uživatelem (zákazníkem):**

1. **E-mailová zpráva (povinný vstup)**
   - Formát: MIME e-mail s textovým obsahem (`text/plain` nebo `text/html`).
   - Obsah: Předmět a text zákaznického dotazu.
   - Metadata: E-mailová adresa odesílatele, identifikátor zprávy a vlákna.

2. **Přílohy (volitelný vstup)**
   - Dokumenty: PDF (`.pdf`).
   - Zvuk: MP3 (`.mp3`), WAV (`.wav`).
   - Obrázky: JPEG (`.jpg`, `.jpeg`), PNG (`.png`).
   - Počet a maximální velikost příloh: Bude stanoveno podle limitů Gmail API a zpracovatelské kapacity aplikace.

3. **Znalostní dokumenty (vstup správce aplikace)**
   - Rozsah: 1–3 dokumenty o fiktivním produktu nebo službě.
   - Účel: Zdroj informací pro RAG vyhledávání.
   - Zpracování: Jednorázové načtení a indexace před spuštěním agenta.

**Hranice a validace:**
- Zpracovávají se pouze nové zprávy z autorizované schránky.
- Podporovány jsou pouze uvedené formáty příloh.
- Neplatné, poškozené nebo příliš velké přílohy musí být bezpečně odmítnuty nebo předány k ruční kontrole.
- Obsah e-mailů a příloh je považován za nedůvěryhodný vstup.
- Zákazník nemusí používat webové rozhraní ani se přihlašovat do aplikace.

### Popiš hlavní user flow od otevření až k výsledku.

- ID: happy_path (povinné)
- Stav: **PŘEDPOKLAD**

1. **Odeslání dotazu:** Zákazník odešle e-mail na adresu zákaznické podpory. Zpráva může obsahovat přílohy PDF, MP3, WAV, JPEG nebo PNG.
2. **Detekce nové zprávy:** Gmail zaznamená příchozí e-mail a prostřednictvím Gmail Watch a Google Pub/Sub odešle notifikaci.
3. **Zahájení zpracování:** Cloud Run Ingress přijme notifikaci a vytvoří úlohu v Cloud Tasks.
4. **Načtení e-mailu:** Worker identifikuje novou zprávu, ověří, zda již nebyla zpracována, a načte její obsah a přílohy pomocí Gmail API.
5. **Analýza obsahu:** Agent zpracuje text zprávy a podporované přílohy a identifikuje zákazníkův požadavek.
6. **Vyhledání informací (RAG):** Agent vyhledá relevantní informace v indexovaných znalostních dokumentech.
7. **Generování odpovědi:** Gemini vytvoří odpověď na základě zákaznického dotazu, příloh a nalezených informací.
8. **Kontrola odpovědi:** Aplikace ověří strukturu odpovědi, příjemce a dostupnost potřebných podkladů.
9. **Odeslání odpovědi:** Agent prostřednictvím Gmail API odešle odpověď do původního e-mailového vlákna.
10. **Uložení výsledku:** Firestore zaznamená stav zpracování, identifikátor odeslané zprávy a dobu zpracování.
11. **Výsledek pro zákazníka:** Zákazník obdrží relevantní odpověď ve stejném e-mailovém vlákně, s cílovou dobou do 120 sekund od přijetí zprávy.

### Co člověk uvidí při úspěchu a jak se k tomu vrátí?

- ID: user_output (povinné)
- Stav: **PŘEDPOKLAD**

**Zákazník:** Po úspěšném zpracování obdrží do své e-mailové schránky srozumitelnou odpověď ve stejném vlákně, ve kterém odeslal dotaz. Odpověď vychází z obsahu zprávy, příloh a relevantních znalostních dokumentů. Cílová doba doručení je do 120 sekund.

**Pracovník zákaznické podpory:** V Gmailu uvidí původní zprávu a automaticky odeslanou odpověď. Ke komunikaci se může kdykoliv vrátit otevřením příslušného e-mailového vlákna.

**Správce aplikace:** V provozních záznamech může dohledat stav zpracování, dobu odezvy, případné chyby a identifikátor odeslané zprávy.

**Uložení výsledku:** E-mailová komunikace zůstává v Gmailu. Firestore uchovává metadata a stav zpracování pro kontrolu a prevenci duplicit.

### Co uvidí při prázdném, chybném či duplicitním vstupu?

- ID: error_scenarios (povinné)
- Stav: **PŘEDPOKLAD**

**1. Prázdný nebo nesrozumitelný e-mail**
- Zákazník odešle zprávu bez konkrétního dotazu.
- Agent odešle žádost o upřesnění požadavku.
- Zpráva je označena jako vyžadující doplnění informací.

**2. Nepodporovaná nebo poškozená příloha**
- Zákazník odešle soubor, který nelze bezpečně zpracovat.
- Agent odpoví, že přílohu nebylo možné přečíst, a požádá o zaslání v podporovaném formátu.
- Chyba je zaznamenána do provozních metadat.

**3. Duplicitní e-mail nebo událost**
- Systém obdrží opakovanou notifikaci ke stejné zprávě.
- Agent ověří stav zpracování ve Firestore.
- Již vyřízenou zprávu přeskočí a neodešle další odpověď.
- Zákazník uvidí pouze jednu odpověď.

**4. Chybějící informace v RAG**
- Agent nenajde dostatečně relevantní informace ve znalostních dokumentech.
- Nevytváří nepodloženou odpověď.
- Zákazník obdrží informaci, že dotaz nelze spolehlivě zodpovědět, případně je zpráva předána k ruční kontrole.

**5. Výpadek externí služby**
- Gmail API, Gemini nebo databáze jsou dočasně nedostupné.
- Systém automaticky opakuje zpracování podle nastavených pravidel.
- Po vyčerpání pokusů označí úlohu jako neúspěšnou.
- Správce může chybu dohledat v provozních záznamech. Zákazník nemusí obdržet okamžitou odpověď.

### Jaké accessibility požadavky splníš?

- ID: accessibility (doplňkové)
- Stav: **PŘEDPOKLAD**

Aplikace v MVP nemá vlastní uživatelské rozhraní. Přístupnost je proto řešena především u automaticky generovaných e-mailových odpovědí.

**Požadavky na přístupnost:**
- Odpovědi musí být srozumitelné, stručné a přehledně strukturované.
- E-maily musí obsahovat textovou verzi (`text/plain`), aby byly čitelné pomocí asistivních technologií.
- Informace nesmí být předávány pouze prostřednictvím obrázků nebo barev.
- Případná HTML verze musí používat sémantickou strukturu a dostatečný kontrast.
- Odpovědi musí být použitelné v běžných e-mailových klientech včetně čteček obrazovky.

**WCAG:** Pro MVP není požadována certifikace shody s WCAG 2.2 AA. Relevantní principy přístupnosti budou zohledněny při generování e-mailů.

Ovládání klávesnicí, formuláře a vlastní navigace nejsou relevantní, protože MVP neobsahuje webové rozhraní.

### Jaké jazyky, měny a časové zóny podporuješ?

- ID: localization (doplňkové)
- Stav: **POTVRZENO**

**Jazyky:**
- Čeština (cs-CZ) – primární jazyk.
- Angličtina (en) – podporovaný jazyk pro testovací e-maily.
- Agent odpovídá ve stejném jazyce, ve kterém zákazník napsal dotaz.

**Měny:**
- CZK – primární měna.
- Převody měn ani zpracování plateb nejsou součástí MVP.

**Časové zóny:**
- Europe/Prague – lokální čas pro uživatele.
- UTC – ukládání časových údajů, logování a měření doby zpracování.

**Stav rozhodnutí:** Pracovní předpoklad. Konkrétní lokalizace není v zadání Alzy stanovena.

### Je nutný offline režim či pomalé spojení?

- ID: offline_mode (doplňkové)
- Stav: **POTVRZENO**

**Offline režim není požadován.**

Aplikace běží v Google Cloud a pro zpracování e-mailů vyžaduje připojení ke Gmail API, Gemini a db (vektorová a nebo postgresová).

Při pomalém nebo přerušeném spojení:
- Neúspěšné požadavky se opakují podle nastavených pravidel.
- Nezpracované úlohy zůstávají ve frontě Cloud Tasks.
- Po obnovení dostupnosti služeb systém pokračuje ve zpracování.
- Při dlouhodobém výpadku může být překročen cílový limit 120 sekund.

**Stav rozhodnutí:** Pracovní předpoklad.

### Kde je wireframe, prototyp, design system nebo Figma?

- ID: ux_prototype (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak bude fungovat první spuštění a onboarding?

- ID: onboarding (doplňkové)
- Stav: **POTVRZENO**
- Vlastník: Vývojář
- Zdroj / důkaz: můj návrh

První spuštění provede správce aplikace jednorázovou konfigurací GCP prostředí a dedikované Gmail schránky.

1. Vytvoří GCP projekt a aktivuje potřebná API.
2. Nastaví Gmail OAuth 2.0 a uloží přístupové údaje do Secret Manageru.
3. Inicializuje Cloud SQL PostgreSQL a databázové migrace.
4. Nasadí Cloud Run Ingress a Worker a nakonfiguruje Pub/Sub a Cloud Tasks.
5. Aktivuje Gmail Watch pro automatickou detekci nových zpráv.
6. Ověří připojení k Vertex AI Gemini a dostupnost modulů Conversation History, RAG a Web Search.
7. Provede test odesláním e-mailu a zkontroluje odpověď ve stejném vlákně.

Po úspěšné inicializaci systém funguje autonomně. Nové nepřečtené e-maily zpracovává bez manuálního zásahu. Cloud Scheduler zajišťuje pravidelnou obnovu Gmail Watch a kontrolu nedokončených úloh.

Aplikace nevyžaduje onboarding koncových uživatelů ani uživatelské účty. Uživatel komunikuje přímo prostřednictvím e-mailu.

## 03 · Funkce, stavy a akceptace

*Cíl:* Přelož chování na testovatelné požadavky s identifikátory.

*Gate:* Každý kritický požadavek má příklad vstupu, výstupu a acceptance criteria.

### Jaké jsou funkční požadavky FR-01, FR-02 ...?

- ID: functional_requirements (povinné)
- Stav: **PŘEDPOKLAD**

**FUNKČNÍ POŽADAVKY – ALZA AI EMAIL AGENT**
FR-01 – Systém musí automaticky detekovat nové e-maily v autorizované Gmail schránce bez ručního spuštění.
FR-02 – Systém musí přijímat notifikace o změnách schránky a identifikovat nové zprávy určené ke zpracování.
FR-03 – Systém musí načíst odesílatele, předmět, obsah zprávy, identifikátor zprávy a identifikátor e-mailového vlákna.
FR-04 – Systém musí podporovat zpracování textových a HTML e-mailů.
FR-05 – Systém musí stahovat a zpracovávat přílohy ve formátech PDF, MP3, WAV, JPEG a PNG.
FR-06 – Systém musí extrahovat informace z podporovaných příloh a použít je při zpracování zákaznického dotazu.
FR-07 – Systém musí umožnit načtení a indexaci 1–3 znalostních dokumentů pro RAG.
FR-08 – Systém musí vytvářet a trvale ukládat vektorové reprezentace znalostních dokumentů.
FR-09 – Systém musí vyhledávat relevantní části znalostních dokumentů podle obsahu zákaznického dotazu.
FR-10 – Systém musí generovat odpověď pomocí AI modelu na základě obsahu e-mailu, příloh a informací získaných pomocí RAG.
FR-11 – Systém musí validovat strukturu vygenerované odpovědi a ověřit splnění pravidel pro bezpečné odesílání.
FR-12 – Systém musí automaticky odeslat odpověď prostřednictvím Gmail API do původního e-mailového vlákna.
FR-13 – Systém musí evidovat stav zpracování každé zprávy, čas zpracování, chyby a identifikátor odeslané odpovědi.
FR-14 – Systém musí rozpoznávat již zpracované zprávy a předcházet duplicitnímu odeslání odpovědi.
FR-15 – Systém musí automaticky opakovat zpracování při dočasném selhání externích služeb podle definovaných pravidel.
FR-16 – Systém musí bezpečně zpracovávat prázdné zprávy, nepodporované, poškozené nebo nadměrně velké přílohy.
FR-17 – Systém musí při nedostatku relevantních informací zabránit nepodloženému odeslání odpovědi a použít definovaný náhradní postup.
FR-18 – Systém musí zaznamenávat provozní metriky a chyby bez ukládání obsahu e-mailů, příloh nebo přístupových údajů do logů.
FR-19 – Systém musí umožnit dohledání neúspěšně zpracovaných zpráv pro kontrolu nebo opakované zpracování.

**BEZPEČNOSTNÍ FUNKČNÍ POŽADAVKY**
FR-20 – Systém musí považovat obsah e-mailů, příloh a RAG dokumentů za nedůvěryhodná data a nesmí umožnit, aby instrukce z těchto zdrojů vyvolaly nepovolené operace (prompt injection).
FR-21 – Systém musí bezpečně spravovat přístupové údaje a nesmí je zpřístupnit AI modelu, zákazníkovi ani v provozních záznamech.
FR-22 – Systém musí ověřovat identitu volajících interních API a odmítat neautorizované požadavky.
FR-23 – Systém musí izolovat kontext jednotlivých e-mailových vláken a zabránit zpřístupnění nesouvisející zákaznické komunikace.
FR-24 – Systém musí určovat příjemce a cílové e-mailové vlákno výhradně prostřednictvím důvěryhodné aplikační logiky, nikoliv podle instrukcí AI modelu.
FR-25 – Systém musí kontrolovat odchozí odpovědi a zabránit odeslání přístupových údajů nebo dat z nesouvisejících zákaznických konverzací.
FR-26 – Systém musí po restartu nebo selhání AI agenta obnovit nedokončené úlohy bez ztráty uložených dat a před opakováním odeslání ověřit, zda odpověď již nebyla odeslána.

### Jaká jsou AC-01, AC-02 ... (Given/When/Then)?

- ID: acceptance_criteria (povinné)
- Stav: **PŘEDPOKLAD**

**AKCEPTAČNÍ KRITÉRIA – ALZA AI EMAIL AGENT**

**AC-01 – Automatická detekce (FR-01)**
- Given: Do autorizované schránky dorazí nový e-mail.
- When: Gmail zaznamená zprávu.
- Then: Systém automaticky zahájí její zpracování.

**AC-02 – Příjem události (FR-02)**
- Given: Gmail odešle notifikaci přes Pub/Sub.
- When: Aplikace ji přijme.
- Then: Identifikuje nové zprávy a zařadí je ke zpracování.

**AC-03 – Načtení e-mailu (FR-03)**
- Given: V Gmailu existuje nová zpráva.
- When: Agent ji načte.
- Then: Získá odesílatele, předmět, obsah, ID zprávy a ID vlákna.

**AC-04 – Text a HTML (FR-04)**
- Given: E-mail obsahuje text/plain nebo text/html.
- When: Agent zprávu zpracuje.
- Then: Získá čitelný text zprávy.

**AC-05 – Podporované přílohy (FR-05)**
- Given: Testovací e-maily obsahují přílohy PDF, MP3, WAV, JPEG a PNG.
- When: Agent postupně zpracuje všechny formáty.
- Then: Každý podporovaný formát úspěšně přečte nebo analyzuje.

**AC-06 – Extrakce informací (FR-06)**
- Given: Příloha obsahuje informaci potřebnou k odpovědi.
- When: Agent přílohu analyzuje.
- Then: Správně použije získanou informaci v odpovědi.

**AC-07 – Indexace dokumentů (FR-07)**
- Given: Jsou připraveny 1–3 znalostní dokumenty.
- When: Proběhne indexace.
- Then: Dokumenty jsou dostupné pro RAG vyhledávání.

**AC-08 – Uložení embeddingů (FR-08)**
- Given: Znalostní dokument byl rozdělen na části.
- When: Proběhne generování embeddingů.
- Then: Embeddingy a identifikace zdrojových částí jsou trvale uloženy.

**AC-09 – RAG vyhledávání (FR-09)**
- Given: Znalostní dokument obsahuje odpověď na testovací otázku.
- When: Agent provede vyhledávání.
- Then: Vrátí relevantní část dokumentu a její zdroj.

**AC-10 – Generování odpovědi (FR-10)**
- Given: Agent má dotaz, obsah příloh a relevantní RAG kontext.
- When: Gemini vytvoří odpověď.
- Then: Odpověď je správná podle referenčních podkladů a odpovídá dotazu.

**AC-11 – Validace odpovědi (FR-11)**
- Given: AI model vrátí neplatnou nebo nepovolenou odpověď.
- When: Aplikace provede validaci.
- Then: Odeslání je zablokováno a chyba zaznamenána.

**AC-12 – Odeslání odpovědi (FR-12)**
- Given: Agent vytvořil platnou odpověď.
- When: Odešle ji prostřednictvím Gmail API.
- Then: Odpověď se zobrazí v původním e-mailovém vlákně.

**AC-13 – Evidence zpracování (FR-13)**
- Given: Agent dokončí zpracování.
- When: Uloží výsledek.
- Then: Databáze obsahuje stav, čas, případnou chybu a ID odeslané zprávy.

**AC-14 – Prevence duplicit (FR-14)**
- Given: Stejná zpráva je opakovaně zařazena ke zpracování.
- When: Agent ověří její stav.
- Then: Neodešle druhou odpověď.

**AC-15 – Opakování při selhání (FR-15)**
- Given: Externí API dočasně neodpovídá.
- When: Zpracování selže.
- Then: Systém automaticky zopakuje úlohu podle nastavených pravidel.

**AC-16 – Neplatný vstup (FR-16)**
- Given: E-mail je prázdný nebo obsahuje neplatnou přílohu.
- When: Agent jej zpracuje.
- Then: Požádá o doplnění informací nebo označí zprávu k ruční kontrole bez pádu aplikace.

**AC-17 – Nedostatek informací (FR-17)**
- Given: RAG nenajde informace potřebné k odpovědi.
- When: Agent vyhodnotí dotaz.
- Then: Nevytvoří nepodložené tvrzení a použije definovaný náhradní postup.

**AC-18 – Provozní metriky (FR-18)**
- Given: Agent dokončí nebo přeruší zpracování.
- When: Vytvoří provozní záznam.
- Then: Log obsahuje výsledek a dobu zpracování, nikoliv obsah e-mailu nebo přístupové údaje.

**AC-19 – Neúspěšné úlohy (FR-19)**
- Given: Zpracování zprávy trvale selže.
- When: Správce kontroluje provozní záznamy.
- Then: Dokáže dohledat úlohu, stav a příčinu selhání.

**AC-20 – Výkon (průřezové kritérium)**
- Given: Testovací zprávy jsou doručeny při dostupných externích službách.
- When: Systém je automaticky zpracuje.
- Then: Alespoň 95 % zpráv je zodpovězeno do 120 sekund od přijetí.

**BEZPEČNOSTNÍ AKCEPTAČNÍ KRITÉRIA**

**AC-21 – Prompt injection (FR-20)**
- Given: E-mail, příloha nebo RAG dokument obsahuje škodlivé instrukce.
- When: Agent obsah zpracuje.
- Then: Nepovolí změnu systémových pravidel ani vykonání neoprávněné operace.

**AC-22 – Ochrana přístupových údajů (FR-21)**
- Given: Aplikace používá přístupové údaje ke Gmailu a externím API.
- When: Agent generuje odpověď nebo nastane chyba.
- Then: Přístupové údaje se neobjeví v promptu, odpovědi ani provozních záznamech.

**AC-23 – Autorizace interních API (FR-22)**
- Given: Neautorizovaný klient odešle požadavek na interní endpoint.
- When: Aplikace požadavek přijme.
- Then: Odmítne jej bez spuštění zpracování.

**AC-24 – Izolace konverzací (FR-23)**
- Given: Ve schránce existují dvě nesouvisející zákaznická vlákna.
- When: Agent zpracovává zprávu z prvního vlákna.
- Then: Nepoužije ani nezpřístupní obsah druhého vlákna.

**AC-25 – Kontrola příloh (FR-16)**
- Given: Příloha má nepodporovaný formát, neplatnou strukturu nebo překračuje povolenou velikost.
- When: Agent ji zpracovává.
- Then: Příloha je bezpečně odmítnuta a její obsah není spuštěn jako kód.

**AC-26 – Ochrana příjemce (FR-24)**
- Given: E-mail nebo AI model obsahuje instrukci změnit příjemce odpovědi.
- When: Agent připravuje odeslání.
- Then: Příjemce a vlákno určuje výhradně aplikační logika.

**AC-27 – Ochrana proti úniku dat (FR-25)**
- Given: Vstup obsahuje požadavek na zveřejnění přístupových údajů nebo komunikace jiného zákazníka.
- When: Agent vytvoří odpověď.
- Then: Odchozí kontrola zabrání odeslání těchto informací.

**AC-28 – Obnova po restartu (FR-26)**
- Given: AI kontejner selže během zpracování zprávy.
- When: Kontejner se restartuje a systém obnoví úlohu.
- Then: Uložená data zůstanou zachována a agent před opakováním odeslání zkontroluje, zda již odpověď neexistuje.

**AC-29 – Ochrana provozních logů (FR-18, FR-21)**
- Given: Během zpracování vznikne chyba obsahující citlivé údaje.
- When: Aplikace vytvoří provozní záznam.
- Then: Log neobsahuje obsah e-mailu, přílohy, přístupový token ani tajný klíč.

### Jaká pravidla, validace a výpočty musí platit?

- ID: business_rules (povinné)
- Stav: **PŘEDPOKLAD**

**BUSINESS RULES (BR)**

BR-01 – Systém zpracovává pouze nové příchozí e-maily z autorizované Gmail schránky. Vlastní odeslané zprávy a již zpracované e-maily ignoruje.
BR-02 – Každá zpráva je jednoznačně identifikována pomocí Gmail Message ID. Systém musí před zpracováním ověřit její stav v PostgreSQL.
BR-03 – Jedna příchozí zpráva smí vyvolat nejvýše jednu automatickou odpověď. Opakované doručení události nesmí způsobit duplicitní odeslání.
BR-04 – Systém přijímá textové a HTML e-maily. HTML obsah musí být bezpečně převeden na čitelný text.
BR-05 – Podporované přílohy jsou PDF, MP3, WAV, JPEG a PNG. Typ přílohy musí být ověřen podle skutečného obsahu, nikoliv pouze přípony souboru.
BR-06 – Přílohy musí splňovat konfigurovatelné limity velikosti a počtu. Nepodporované, poškozené nebo nadlimitní přílohy nesmí způsobit pád aplikace.
BR-07 – Systém musí při zpracování zákaznického dotazu využít relevantní informace ze znalostních dokumentů prostřednictvím RAG.
BR-08 – RAG vyhledávání smí používat pouze schválené a indexované znalostní dokumenty. Každý nalezený úsek musí mít identifikovatelný zdroj.
BR-09 – Pokud dostupné informace nestačí k věcně podložené odpovědi, systém nesmí vymýšlet fakta. Použije definovanou náhradní odpověď nebo označí zprávu k ruční kontrole.
BR-10 – AI model vytváří pouze obsah odpovědi. Příjemce, Gmail Thread ID a oprávnění k odesílání určuje výhradně aplikační logika.
BR-11 – Obsah e-mailů, příloh a znalostních dokumentů je nedůvěryhodný. Instrukce obsažené v těchto datech nesmí měnit bezpečnostní pravidla ani vyvolávat nepovolené operace.
BR-12 – Před odesláním musí odpověď projít validací struktury, povoleného příjemce a pravidel ochrany citlivých údajů. Neplatná odpověď se neodešle.
BR-13 – Odpověď se odesílá výhradně do původního e-mailového vlákna prostřednictvím Gmail API.
BR-14 – Cílová doba zpracování je 120 sekund od přijetí e-mailu do odeslání odpovědi. Doba zpracování se vypočítá jako čas odeslání odpovědi minus čas přijetí zprávy.
BR-15 – Při dočasném výpadku externí služby systém opakuje zpracování podle konfigurovatelného počtu pokusů a prodlev. Trvalé chyby označí k následnému řešení.
BR-16 – Před opakováním odeslání po nejasném výsledku Gmail API musí systém ověřit, zda odpověď již nebyla odeslána.
BR-17 – PostgreSQL uchovává stav zpracování, identifikátory zpráv, výsledky úloh a provozní metadata. Rozšíření pgvector uchovává embeddingy znalostních dokumentů.
BR-18 – Pád nebo restart AI kontejneru nesmí způsobit ztrátu trvale uložených dat. Nedokončené úlohy musí být možné obnovit.
BR-19 – Přístupové údaje, obsah zákaznických zpráv a přílohy nesmí být zapisovány do provozních logů.
BR-20 – Systém musí používat pouze nezbytná oprávnění pro Gmail, databázi a AI služby. Neautorizované požadavky musí odmítnout.

**VÝPOČTY A METRIKY**

M-01 – Doba zpracování (s) = čas odeslání odpovědi − čas přijetí e-mailu.
M-02 – Úspěšnost zpracování (%) = (počet úspěšně zpracovaných e-mailů / počet podporovaných příchozích e-mailů) × 100.
M-03 – Splnění časového limitu (%) = (počet správně vyřízených e-mailů do 120 sekund / počet podporovaných příchozích e-mailů) × 100.
M-04 – Chybovost (%) = (počet neúspěšně zpracovaných e-mailů / počet podporovaných příchozích e-mailů) × 100.
M-05 – Náklady na e-mail = celkové náklady na zpracování / počet zpracovaných e-mailů.

**Poznámka:** Pravidla představují návrh pro MVP. Konkrétní limity příloh, počet opakování a způsob vyhodnocení relevance RAG musí být stanoveny při implementaci.

### Jaké nepovolené stavy nesmějí nikdy vzniknout?

- ID: forbidden_states (povinné)
- Stav: **PŘEDPOKLAD**

**NEPOVOLENÉ STAVY (FS)**

FS-01 – Jedna příchozí zpráva nesmí způsobit odeslání více automatických odpovědí, ani při opakovaném doručení události nebo restartu agenta.
FS-02 – Odpověď nesmí být odeslána jinému příjemci nebo do jiného e-mailového vlákna.
FS-03 – Agent nesmí zveřejnit přístupové tokeny, hesla, API klíče ani jiné tajné údaje.
FS-04 – Agent nesmí zpřístupnit obsah e-mailů nebo příloh jiného zákaznického vlákna.
FS-05 – Instrukce vložené do e-mailu, přílohy nebo RAG dokumentu nesmí způsobit nepovolenou operaci ani změnu bezpečnostních pravidel.
FS-06 – Agent nesmí odeslat faktická tvrzení, která nejsou podložena dostupnými informacemi, jako ověřené skutečnosti.
FS-07 – Systém nesmí odeslat odpověď, která neprošla povinnou validací.
FS-08 – Nepodporovaná, poškozená nebo nebezpečná příloha nesmí být spuštěna jako kód ani způsobit nekontrolované selhání aplikace.
FS-09 – Neautorizovaný klient nesmí spustit zpracování e-mailu ani získat přístup k interním API.
FS-10 – Obsah zákaznických e-mailů, příloh a přístupové údaje nesmí být uložen do provozních logů.
FS-11 – Úloha nesmí být označena jako úspěšně odeslaná, pokud odeslání nebylo potvrzeno nebo jinak ověřeno.
FS-12 – Pád nebo restart AI kontejneru nesmí způsobit ztrátu trvale uložených databázových dat.
FS-13 – Neúspěšná úloha nesmí zůstat bez evidence ve stavu, který znemožňuje její dohledání nebo bezpečné obnovení.
FS-14 – Agent nesmí zpracovávat e-maily mimo autorizovanou schránku ani provádět operace nad daty, ke kterým nemá oprávnění.

### Jaké entity mění stav a jaké přechody jsou povolené?

- ID: entity_states (povinné)
- Stav: **PŘEDPOKLAD**

**ENTITY STATES – ALZA AI EMAIL AGENT**

**1. EmailJob – zpracování e-mailu**

Hlavní posloupnost:
- RECEIVED → QUEUED → PROCESSING → READY_TO_SEND → SENDING → SENT

Alternativní přechody:
- PROCESSING → RETRY_PENDING → QUEUED
- PROCESSING → REVIEW_REQUIRED
- PROCESSING → FAILED
- SENDING → RETRY_PENDING (pouze při potvrzeném neodeslání)
- SENDING → DELIVERY_UNKNOWN
- DELIVERY_UNKNOWN → SENT (odeslání dohledáno v Gmailu)
- DELIVERY_UNKNOWN → REVIEW_REQUIRED (výsledek nelze bezpečně ověřit)
- FAILED → QUEUED (pouze ruční opakování)

Stav SENT je konečný. Opakované události nesmí vytvořit další odpověď.

**2. KnowledgeDocument – znalostní dokument pro RAG**

Hlavní posloupnost:
- NEW → INDEXING → INDEXED

Alternativní přechody:
- INDEXING → FAILED
- FAILED → INDEXING (opakování indexace)
- INDEXED → INDEXING (aktualizace dokumentu)

Při neúspěšné aktualizaci nesmí být neúplný index použit pro vyhledávání.

**3. Attachment – příloha e-mailu**

Přílohy se v MVP zpracovávají v rámci EmailJob a nemají samostatný persistentní stav.

**Pravidla stavových přechodů:**
- Každý přechod EmailJob musí být zaznamenán v PostgreSQL.
- Souběžné procesy nesmí převzít stejnou aktivní úlohu.
- Opakované zpracování musí respektovat nastavený počet pokusů.
- Stav SENT lze nastavit pouze po potvrzení nebo ověření odeslání.
- Při neznámém výsledku odeslání se nesmí automaticky odeslat další odpověď bez kontroly Gmailu.
- Restart kontejneru nesmí způsobit ztrátu stavu.
- Nepovolené přechody musí aplikace odmítnout.

### Která role smí kterou akci a nad čími daty?

- ID: permissions_matrix (povinné)
- Stav: **PŘEDPOKLAD**

**MATICE ROLÍ A OPRÁVNĚNÍ – ALZA AI EMAIL AGENT**

**1. Zákazník (vlastník dotazu)**
- Může odesílat e-maily a přílohy.
- Může číst odpovědi doručené do vlastní schránky.
- Nemůže přistupovat k interním datům aplikace ani ke komunikaci jiných zákazníků.

**2. Pracovník zákaznické podpory**
- Může číst a vyřizovat zprávy v autorizované Gmail schránce podle přidělených oprávnění.
- Může kontrolovat automatické odpovědi a řešit nevyřízené požadavky.
- Nemůže měnit konfiguraci aplikace ani spravovat infrastrukturu.

**3. Správce aplikace**
- Může spravovat konfiguraci, integrace a znalostní dokumenty pro RAG.
- Může sledovat stav zpracování a provozní metriky.
- Může spravovat nasazení a oprávnění služeb.
- Nemá automaticky přístup k obsahu zákaznických e-mailů.

**4. Support administrátor**
- Může zobrazovat provozní logy a chybové stavy.
- Může kontrolovat a bezpečně opakovat neúspěšné úlohy.
- Nemůže měnit bezpečnostní pravidla ani získávat přístupové údaje.
- Nemá automaticky přístup k zákaznickému obsahu.

**5. AI agent (Worker)**
- Může číst zprávy a přílohy pouze z autorizované Gmail schránky.
- Může vyhledávat informace ve schválených RAG dokumentech.
- Může generovat a odesílat validované odpovědi původním odesílatelům do správných vláken.
- Může ukládat a aktualizovat stav vlastních úloh v PostgreSQL.
- Nesmí měnit konfiguraci, přístupová oprávnění ani odesílat data neoprávněným příjemcům.

**6. Ingress (systémová služba)**
- Může přijímat autorizované události a předávat úlohy ke zpracování.
- Nemá oprávnění číst zákaznické e-maily ani volat AI model.
- Nemůže odesílat odpovědi.

**ŘÍZENÍ PŘÍSTUPU**
- Gmail OAuth 2.0 – přístup k autorizované schránce.
- Google Cloud IAM – oprávnění cloudových služeb.
- PostgreSQL – oddělená databázová oprávnění.
- Aplikační pravidla – kontrola povolených operací a příjemců.
- Výchozí pravidlo: všechny nepovolené operace jsou zamítnuty.

**MVP:** Aplikace nemá vlastní uživatelské účty ani RBAC. Oprávnění jsou řízena externími systémy a aplikační logikou.

### Co se stane při opakovaném kliknutí nebo stejném požadavku?

- ID: idempotency_behaviour (doplňkové)
- Stav: **PŘEDPOKLAD**

Každý příchozí e-mail je jednoznačně identifikován pomocí Gmail Message ID a identifikátoru schránky.

- Opakované doručení stejné události nesmí vytvořit další úlohu ani duplicitní odpověď.
- Systém před zpracováním ověří stav zprávy v PostgreSQL.
- Pokud je zpráva právě zpracovávána, další pokus ji nepřevezme.
- Pokud již byla odpověď odeslána, opakovaný požadavek se přeskočí.
- Pokud je výsledek odeslání neznámý, systém nejprve ověří stav v Gmailu.
- Opakování neúspěšné úlohy musí navázat na uložený stav.

Cílem je idempotentní zpracování a prevence duplicitních odpovědí i při restartu agenta.

### Co když dva uživatelé upraví stejný objekt současně?

- ID: concurrency_behaviour (doplňkové)
- Stav: **PŘEDPOKLAD**

MVP neobsahuje uživatelské rozhraní pro souběžné úpravy objektů. Souběh však může nastat při zpracování stejného e-mailu více instancemi agenta.

- Jednu e-mailovou úlohu smí současně zpracovávat pouze jeden worker.
- Převzetí úlohy musí být atomické prostřednictvím PostgreSQL.
- Ostatní workery musí respektovat aktuální stav a zámek úlohy.
- Při pádu workeru musí být možné po vypršení jeho rezervace úlohu bezpečně obnovit.
- Aktualizace znalostních dokumentů nesmí zpřístupnit neúplně vytvořený RAG index.
- Konfliktní změny musí být odmítnuty nebo bezpečně zopakovány.

Databáze představuje jediný zdroj pravdy pro stav zpracování.

### Kdy systém posílá e-mail, push či notifikaci?

- ID: notifications (doplňkové)
- Stav: **PŘEDPOKLAD**

**1. Automatická e-mailová odpověď**
- Po úspěšném zpracování zákaznického dotazu.
- Odesílá se do původního Gmail vlákna.
- Cílová doba odeslání je do 120 sekund od přijetí zprávy.

**2. Žádost o doplnění informací**
- Pokud je dotaz nejasný, prázdný nebo nelze zpracovat důležitou přílohu.
- Zákazník obdrží žádost o upřesnění podle definovaných pravidel.

**3. Interní provozní události**
- Gmail Watch a Pub/Sub spouští automatické zpracování.
- Chyby a neúspěšné úlohy jsou zaznamenávány do provozních záznamů.

**Mimo MVP:** Push notifikace, SMS a samostatné e-mailové upozornění administrátorovi.

### Jak funguje vyhledávání, řazení, filtry a stránkování?

- ID: search_filtering (doplňkové)
- Stav: **PŘEDPOKLAD**

Vyhledávání je součástí RAG a probíhá automaticky při zpracování zákaznického e-mailu.

**Vyhledávání:**
- Dotaz zákazníka se převede na embedding.
- PostgreSQL s pgvector vyhledá významově podobné části znalostních dokumentů.
- Výsledky se řadí podle vektorové podobnosti.
- Agent použije nejvýše 3 nejrelevantnější části dokumentů.

**Filtrování:**
- Vyhledávají se pouze aktivní a schválené znalostní dokumenty.
- Každý výsledek musí obsahovat identifikaci zdroje.
- Nedostatečně relevantní výsledky nesmí být prezentovány jako ověřená odpověď.

**Stránkování:**
- Není součástí MVP.
- RAG vrací omezený počet výsledků (Top-K).
- Aplikace nemá uživatelské rozhraní pro procházení výsledků.

### Jaké akce musí mít auditní stopu?

- ID: audit_events (doplňkové)
- Stav: **PŘEDPOKLAD**

Auditní stopu musí mít následující události:

- Přijetí a identifikace nového e-mailu.
- Zahájení a dokončení zpracování.
- Zpracování příloh a případné chyby.
- Provedení RAG vyhledávání a identifikace použitých zdrojů.
- Vygenerování a validace AI odpovědi.
- Odeslání odpovědi včetně Gmail Message ID.
- Opakované pokusy a přeskočení duplicitních úloh.
- Zamítnutí nepovolené operace.
- Selhání zpracování a změny stavů úloh.
- Indexace, aktualizace a odstranění znalostních dokumentů.
- Změny konfigurace a přístupových oprávnění, pokud jsou prováděny.

**Auditní záznam obsahuje:** Čas, identifikátor úlohy, typ události, výsledek a identitu vykonávající služby.

**Bezpečnost:** Auditní záznamy nesmí obsahovat přístupové tokeny, obsah zákaznických e-mailů ani přílohy. Musí být chráněny proti neoprávněným změnám.

### Jaké jsou hraniční stavy, zneužití nebo cancel flow?

- ID: edge_cases (doplňkové)
- Stav: **PŘEDPOKLAD**

**Hraniční a chybové scénáře:**

1. Prázdný nebo nesrozumitelný e-mail – žádost o upřesnění.
2. Nepodporovaná, poškozená nebo příliš velká příloha – bezpečné odmítnutí nebo ruční kontrola.
3. Chybějící relevantní RAG informace – zákaz nepodložené odpovědi.
4. Duplicitní událost – přeskočení již zpracované zprávy.
5. Současné zpracování stejné zprávy – pouze jeden worker může převzít úlohu.
6. Výpadek Gmail API, Gemini nebo databáze – opakování podle nastavených pravidel.
7. Pád kontejneru – obnovení nedokončené úlohy z uloženého stavu.
8. Neznámý výsledek odeslání – ověření v Gmailu před případným opakováním.
9. Prompt injection v e-mailu, příloze nebo RAG dokumentu – nepovolené operace musí být zablokovány.
10. Pokus získat cizí komunikaci nebo přístupové údaje – odmítnutí a bezpečnostní záznam.
11. Neautorizované API volání – odmítnutí požadavku.
12. Vyčerpání limitů externích API – omezení zátěže, opakování nebo kontrolované selhání.

**Cancel flow:**
- Nezahájenou úlohu lze označit jako CANCELLED.
- Zrušení probíhající úlohy musí zabránit zahájení dalších operací.
- Již odeslaný e-mail nelze zrušením úlohy vzít zpět.
- Automatické zrušení nesmí způsobit nekonzistentní stav nebo duplicitní odpověď.

### Zapiš vazby FR -> AC -> TEST -> implementační ticket.

- ID: traceability (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

## 04 · NFR, SLA, kapacita a rozpočet

*Cíl:* Změň vágní „rychlé a bezpečné“ na měřitelné cíle.

*Gate:* Neznámé kritické hodnoty jsou explicitní otázky s vlastníkem.

### Jaká je cílová odezva (např. p95) a jak ji změříš?

- ID: performance_target (povinné)
- Stav: **PŘEDPOKLAD**

**Cílová odezva:** p95 ≤ 120 sekund od přijetí e-mailu do odeslání odpovědi.

**Měřená operace:** Kompletní zpracování e-mailu včetně příloh, RAG vyhledávání, generování a odeslání odpovědi.

**Způsob měření:**
- Začátek: Čas přijetí zprávy do Gmailu.
- Konec: Čas úspěšného odeslání odpovědi.
- Výpočet: Doba odezvy = konec − začátek.
- Vyhodnocení: p50, p95, maximum a procento odpovědí do 120 sekund.

**Testovací prostředí:** Google Compute Engine, Docker Compose, PostgreSQL + pgvector, Gmail API a Gemini.

**Testovací zátěž:** Minimálně 30 e-mailů, souběžně 1–5 zpráv, včetně všech podporovaných formátů příloh.

**Stav:** Pracovní předpoklad. Limit 120 sekund vychází ze zadání, p95 je navržené kritérium.

### Kolik uživatelů, požadavků a špiček očekáváš?

- ID: traffic_estimate (povinné)
- Stav: **PŘEDPOKLAD**

**Odhad provozu pro PoC:**
- Počet e-mailových schránek: 1.
- Počet správců: 1.
- Počet zákazníků: Není omezen konkrétním počtem účtů.
- Očekávaný objem: 10–30 testovacích e-mailů denně.
- Průměrná zátěž: Méně než 1 e-mail za minutu.
- Testovací špička: 5 současně přijatých zpráv.
- Peak factor: Přibližně 5× oproti testovací souběžné zátěži jedné zprávy.
- Velikost textového vstupu: Obvykle jednotky až desítky KB.
- Maximální velikost přílohy pro PoC: Navrhovaný limit 10 MB.
- Podporované přílohy: PDF, MP3, WAV, JPEG, PNG.

**Kapacitní omezení:** Výkon VM, paměť, limity Gmail API, Gemini a velikost příloh.

### Jaký je požadavek na dostupnost a měřené období?

- ID: availability_target (povinné)
- Stav: **PŘEDPOKLAD**

**Cílová dostupnost PoC:** 99 % během plánovaného 72hodinového testovacího období.

**Kritická funkce:** Automatické přijetí, zpracování a odeslání odpovědi na podporovaný e-mail.

**Způsob měření:**
- Pravidelná kontrola dostupnosti aplikace každou minutu.
- End-to-end test zpracování e-mailu.
- Evidence výpadků a neúspěšných úloh.
- Výpočet dostupnosti jako podíl úspěšných kontrol z celkového počtu kontrol.

**Obnova provozu:**
- Automatický restart kontejnerů.
- Zachování databázových dat na persistentním disku.
- Opakování nedokončených úloh.
- Kontrola stavu po restartu.

**Omezení:** Jedna VM představuje společný bod selhání. Vysoká dostupnost ani smluvní SLA nejsou součástí PoC. Výpadky externích API se evidují samostatně.

### Jaké je RPO a RTO pro důležitá data?

- ID: recovery_targets (povinné)
- Stav: **PŘEDPOKLAD**

**RPO (Recovery Point Objective): 24 hodin.**
Maximální přípustná ztráta trvale uložených databázových dat při havárii celé VM nebo disku.

**RTO (Recovery Time Objective): 4 hodiny.**
Cílová maximální doba obnovení aplikace po závažném výpadku.

**Důležitá data:**
- PostgreSQL: Stavy zpracování e-mailů a historie úloh.
- PostgreSQL + pgvector: Znalostní dokumenty a embeddingy.
- Gmail: Původní e-maily a odeslané odpovědi.

**Způsob obnovy:**
- Persistentní disk pro PostgreSQL.
- Denní konzistentní záloha databáze.
- Obnova databáze ze zálohy.
- Opětovné spuštění Docker Compose.
- Kontrola Gmailu a obnovení nedokončených úloh.
- Možnost opětovné indexace RAG dokumentů.

**Ověření:** Test obnovení databáze a aplikace ze zálohy.

### Jak dlouho a proč držíš data, logy a zálohy?

- ID: retention_policy (povinné)
- Stav: **PŘEDPOKLAD**

**Navržená retenční politika pro PoC:**

**1. E-maily a přílohy**
- Originály zůstávají v Gmailu podle pravidel schránky.
- Aplikace přílohy zpracovává dočasně.
- Dočasné soubory se odstraní po dokončení nebo selhání zpracování.

**2. PostgreSQL – provozní data**
- Stavy úloh a technická metadata: 30 dní.
- Účel: Prevence duplicit, diagnostika a opakované zpracování.
- Po ukončení PoC se testovací data odstraní.

**3. RAG dokumenty a embeddingy**
- Uchovávají se po dobu testování.
- Po aktualizaci nebo odstranění dokumentu se aktualizuje i jeho index.
- Po ukončení PoC se odstraní testovací dokumenty a embeddingy.

**4. Provozní a auditní logy**
- Retence: 30 dní.
- Obsah: Čas, ID úlohy, stav, operace a typ chyby.
- Bez obsahu zákaznických zpráv, příloh a přístupových údajů.

**5. Databázové zálohy**
- Frekvence: Jednou denně.
- Retence: 7 dní.
- Účel: Obnova při havárii nebo poškození databáze.
- Zálohy musí být uložené odděleně od VM.

**6. Ochrana dat**
- Pro PoC se používají syntetická data.
- Přístup k datům a zálohám mají pouze autorizované identity.
- Retenční politika musí být před použitím skutečných osobních údajů znovu posouzena.

### Jaký je měsíční strop nákladů a kdo hlídá odchylky?

- ID: budget (povinné)
- Stav: **PŘEDPOKLAD**

**Navržený měsíční rozpočet PoC: 50 USD.**

- Financování: Google Cloud Free Trial (kredit 300 USD / 90 dní).
- Náklady: Compute Engine VM, persistentní disk, zálohy, Gemini API a síťový provoz.
- Monitoring: Google Cloud Billing.
- Upozornění: Při dosažení 50 %, 80 % a 100 % rozpočtu.
- Odpovědnost: Vývojář aplikace.
- Kontrola: Denně během vývoje a testování.

**Při překročení rozpočtu:**
- Zastavit nepotřebné testování a AI volání.
- Vypnout nevyužívanou VM.
- Prověřit náklady jednotlivých služeb.

Běžná rozpočtová upozornění automaticky nezastavují čerpání kreditu. Rozpočet 50 USD je návrhová hodnota, nikoliv garantovaný cenový strop.

### Jak se provoz může změnit za 3, 12 a 24 měsíců?

- ID: growth_projections (doplňkové)
- Stav: **PŘEDPOKLAD**

**3 měsíce – PoC / pilot**
- Jedna Gmail schránka.
- 10–30 e-mailů denně.
- Jedna Compute Engine VM.
- Docker Compose + PostgreSQL + pgvector.
- Jeden AI worker s omezeným souběhem.
- Ruční správa znalostních dokumentů.

**12 měsíců – Možný rozšířený provoz**
- Modelový scénář: 100 e-mailů denně.
- Více znalostních dokumentů.
- Oddělení aplikačního zpracování od databáze.
- Možný přechod na Cloud Run a spravovaný PostgreSQL.
- Automatizované nasazování, monitoring a zálohování.

**24 měsíců – Možný produkční růst**
- Modelový scénář: 500 e-mailů denně.
- Více paralelních workerů.
- Samostatná fronta úloh.
- Horizontální škálování aplikační vrstvy.
- Pokročilé sledování výkonu a nákladů.
- Možné rozšíření o další schránky a integrace.

**Poznámka:** Uvedené objemy jsou kapacitní scénáře, nikoliv potvrzená prognóza. Škálování bude vycházet ze skutečného zatížení.

### Kolik dat vznikne denně a ročně? Zahrň zálohy.

- ID: storage_estimate (doplňkové)
- Stav: **PŘEDPOKLAD**

**Vstupní předpoklady:**
- 30 zpracovaných e-mailů denně.
- 2–10 KB provozních metadat na jednu zprávu.
- Retence provozních dat: 30 dní.
- Znalostní báze: 1–3 dokumenty.
- Přílohy nejsou trvale ukládány.

**Odhad dat PostgreSQL:**
- Denně: 60–300 KB.
- Měsíčně: 1,8–9 MB.
- Ročně bez mazání: 22–110 MB.
- Při 30denní retenci: Přibližně 1,8–9 MB aktivních metadat.

**Další úložiště:**
- RAG dokumenty a embeddingy: Jednotky až desítky MB.
- Databázové indexy a režie PostgreSQL: Dodatečná kapacita.
- Dočasné přílohy: Podle souběhu a velikosti souborů.
- Docker image, systémové logy a OS: Jednotky GB.

**Zálohování:**
- Frekvence: Jednou denně.
- Retence: 7 dní.
- Umístění: Oddělené úložiště mimo VM.
- Odhad záloh: Až přibližně 7 úplných kopií databáze před kompresí.

**Doporučená kapacita:**
- Persistentní disk VM: 30 GB.
- Monitoring zaplnění disku.
- Automatické odstranění dočasných souborů.

Výpočty představují orientační odhad; skutečné využití závisí na indexech, logách a velikosti příloh.

### Jaké kvóty, rate limity a SLA mají externí služby?

- ID: external_limits (doplňkové)
- Stav: **PŘEDPOKLAD**

**1. Gmail API**
- Kvóty jsou řízeny na úrovni projektu a uživatele.
- Pro novější projekty: 1 200 000 quota units/min/projekt a 6 000 quota units/min/uživatel.
- Jednotlivé API operace spotřebovávají různý počet jednotek.
- Platí také samostatné limity odesílání e-mailů.
- Při překročení limitu systém použije exponential backoff.

**2. Gemini / Vertex AI**
- Limity závisí na zvoleném modelu, regionu a projektu.
- Je nutné ověřit dostupné kvóty před nasazením.
- Aplikace musí ošetřit chyby 429, 5xx a timeouty.
- Počet současných AI požadavků bude omezen konfigurací workeru.

**3. Google Pub/Sub**
- Služba má kvóty pro přenos zpráv a požadavky.
- Doručení může být opakované nebo zpožděné.
- Systém musí podporovat idempotentní zpracování.

**4. Google Compute Engine**
- Výkon závisí na zvoleném typu VM.
- Jedna VM představuje společný bod selhání.
- Výpadek VM může způsobit nedostupnost aplikace.

**5. SLA a závislosti**
- Dostupnost Gmail API a Gemini je závislá na poskytovateli.
- Cílových 120 sekund není garantováno při výpadku nebo překročení kvót.
- PoC nemá vlastní smluvní SLA.

Poznámka: Konkrétní kvóty Gemini a smluvní SLA musí být ověřeny pro zvolené služby.

### Kde je výpočet kapacity CPU/RAM/DB/sítě a vstupní předpoklady?

- ID: capacity_estimate (doplňkové)
- Stav: **PŘEDPOKLAD**

**Doporučená infrastruktura PoC:**
- Google Compute Engine: e2-medium.
- CPU: 2 sdílené vCPU (s přibližně 1 vCPU trvalého výkonu).
- RAM: 4 GB.
- Disk: 30 GB Persistent Disk.
- Orchestrace: Docker Compose.
- Kontejnery: AI Worker + PostgreSQL/pgvector.

**Orientační rozdělení RAM:**
- Operační systém a Docker: 0,5–1 GB.
- PostgreSQL + pgvector: 0,3–0,8 GB.
- AI Worker a zpracování příloh: 0,5–1,5 GB.
- Zbývající paměť: Rezerva pro špičky.

**Kapacitní předpoklady:**
- 10–30 e-mailů denně.
- Nejvýše 2 současně zpracovávané zprávy při prvním testu.
- Testovací špička: 5 doručených e-mailů.
- Maximální velikost jedné přílohy: Navržených 10 MB.
- LLM inference běží externě přes Gemini API.
- RAG využívá PostgreSQL + pgvector.

**Databáze:**
- Desítky až stovky MB provozních a znalostních dat.
- Persistentní úložiště.
- Indexované identifikátory e-mailů a stavů úloh.

**Síť:**
- Odchozí HTTPS komunikace s Gmail API a Gemini.
- Pub/Sub pro příjem událostí.
- PostgreSQL dostupné pouze v interní Docker síti.
- Datový přenos závisí na velikosti příloh a AI požadavků.

**Ověření kapacity:**
- Sledovat CPU, RAM, disk a síť během testování.
- Provést test 1, 2 a 5 současně doručených e-mailů.
- Měřit p95 odezvy a počet úspěšných zpracování.
- Při nedostatku paměti snížit souběh nebo navýšit VM.

Pozn.: Jde o počáteční sizing, který musí potvrdit zátěžové testy.

### Jaké jsou dominantní jednotkové náklady (na uživatele/job/request)?

- ID: cost_model (doplňkové)
- Stav: **PŘEDPOKLAD**
- Vlastník: Vývojář
- Zdroj / důkaz: můj návrh

Základní jednotkou nákladů je jeden zpracovaný příchozí e-mail (email job), nikoliv jeden uživatel.

Dominantní náklady:

1. Vertex AI Gemini – generování odpovědí, multimodální zpracování příloh a spotřeba vstupních/výstupních tokenů.
2. Cloud SQL PostgreSQL – průběžné náklady na databázovou instanci, úložiště, evidenci úloh a RAG pomocí pgvector.
3. Cloud Run Worker – využitý CPU čas a paměť při zpracování e-mailů.
4. Vertex AI Embeddings – generování embeddingů pro RAG dokumenty a vyhledávací dotazy.
5. Live Web Search – případné poplatky za Google Search grounding podle použitého modelu a aktuálního ceníku.
6. Pub/Sub, Cloud Tasks, Cloud Logging a Secret Manager – doplňkové provozní náklady podle využití.

Náklady na jeden e-mail závisí zejména na velikosti příloh, délce historie vlákna, počtu tokenů a využití RAG nebo Web Search.

Pro optimalizaci používáme omezený kontext, validační limity příloh, podmíněné volání RAG/Web Search, Cloud Run autoscaling a limity souběžného zpracování.

Skutečnou jednotkovou cenu určíme měřením během PoC. Cloud SQL představuje fixní náklad i při nízkém provozu.

### Jaký má každá klíčová komponenta latency budget?

- ID: latency_budget (doplňkové)
- Stav: **PŘEDPOKLAD**

Celkový cíl: odpověď do 120 sekund od přijetí e-mailu v Gmailu do potvrzeného odeslání odpovědi.

Návrhový latency budget pro jeden e-mail:

1. Gmail Watch → Pub/Sub → Cloud Run Ingress: 10 s
2. Cloud Tasks Sync Queue + Gmail synchronizace: 10 s
3. Cloud Tasks Process Queue + spuštění Workeru: 5 s
4. Načtení e-mailu, příloh a Conversation History: 10 s
5. Validace a příprava příloh: 10 s
6. RAG retrieval a případný Live Web Search: 15 s
7. Vertex AI Gemini – analýza a generování odpovědi: 40 s
8. Validace odpovědi, Gmail API Send a uložení výsledku: 10 s
9. Rezerva na síťovou latenci a variabilitu: 10 s

Celkem: 120 sekund.

Výchozí aplikační deadline Workeru je maximálně 100 sekund a Cloud Run HTTP timeout 110 sekund. Čas od přijetí e-mailu se musí měřit samostatně, protože zahrnuje také notifikaci a čekání ve frontě.

Jednotlivé hodnoty jsou návrhové, nikoliv naměřené. Po implementaci je upravíme podle end-to-end testů a metrik p50, p95 a maximum. Při překročení deadline systém nesmí nekontrolovaně opakovat odeslání.

### Kde a podle koho bude limit počtu požadavků?

- ID: rate_limiting (doplňkové)
- Stav: **PŘEDPOKLAD**

Rate limiting bude řízen na úrovni Cloud Tasks, Cloud Run a externích API.

1. Cloud Tasks Sync Queue:
- Maximálně 1 současná synchronizace jedné Gmail schránky.
- Zabraňuje souběžným konfliktním synchronizacím.

2. Cloud Tasks Process Queue:
- Výchozí limit 3 současně zpracovávaných e-mailů.
- Maximální rychlost dispatchingu bude nastavena podle naměřené kapacity a API kvót.
- Při přetížení zůstávají úlohy ve frontě.

3. Cloud Run Worker:
- Max instances: 3.
- Concurrency: 1 požadavek na instanci.
- Kapacitu lze postupně zvýšit bez změny aplikační logiky.

4. Externí API:
- Gmail API a Vertex AI Gemini respektují dostupné kvóty.
- Při HTTP 429 nebo dočasných chybách aplikace používá omezený retry s exponential backoff.

5. Ochrana proti duplicitám:
- Každý e-mail je identifikován pomocí mailbox_id a gmail_message_id.
- Databázová rezervace brání souběžnému zpracování stejné zprávy.
- Vlastní a automatické odpovědi se filtrují.

Pro PoC není požadován uživatelský rate limiting, protože systém používá jednu dedikovanou Gmail schránku bez veřejného uživatelského API.

### Jaké regulatorní/národní či smluvní standardy platí?

- ID: compliance_targets (doplňkové)
- Stav: **PŘEDPOKLAD**

Pro aplikaci Reply McFly jsou relevantní následující bezpečnostní a regulatorní požadavky:

1. GDPR – nařízení EU 2016/679:
- Ochrana osobních údajů obsažených v e-mailech, přílohách a historii komunikace.
- Minimalizace rozsahu zpracovávaných a ukládaných údajů.
- Omezení doby uchovávání dat.
- Zabezpečení přístupu a zpracování osobních údajů.
- Posouzení rolí správce a zpracovatele a podmínek využití cloudových služeb.

2. Bezpečnost cloudové infrastruktury:
- IAM a princip nejnižších oprávnění.
- OAuth 2.0 pro Gmail API.
- Secret Manager pro přístupové údaje.
- Autentizované Cloud Run endpointy pomocí OIDC.
- Šifrovaná komunikace přes TLS.
- Logování bez obsahu e-mailů, příloh a přístupových tokenů.

3. Bezpečnost AI:
- Ochrana proti prompt injection.
- Oddělení nedůvěryhodného obsahu od systémových instrukcí.
- Zákaz předávání soukromého obsahu externímu webovému vyhledávání.
- Validace příloh před AI zpracováním.
- Kontrolované odesílání odpovědí prostřednictvím backendu.

4. Provozní rozsah PoC:
- Používání syntetických testovacích dat.
- Omezený přístup k dedikované Gmail schránce.
- Žádné veřejné uživatelské rozhraní.
- Před produkčním provozem doplnit antivirovou kontrolu, retenční pravidla a posouzení ochrany osobních údajů.

Formální certifikace ISO 27001, SOC 2 ani zvláštní odvětvové regulatorní standardy nejsou pro samotné PoC stanoveny.

### Seznam NFR-01 ... a vazby na testy a metriky.

- ID: nfr_references (doplňkové)
- Stav: **PŘEDPOKLAD**

NEFUNKČNÍ POŽADAVKY – REPLY MCFLY

NFR-01 – Výkon a latence
Požadavek: Odeslat odpověď do 120 sekund od přijetí e-mailu.
Metriky: End-to-end latency, p50, p95, maximum.
Test: Zpracování e-mailů s různými typy příloh a kombinací kontextových zdrojů.

NFR-02 – Škálovatelnost
Požadavek: Zpracovávat více e-mailů souběžně pomocí Cloud Run a Cloud Tasks.
Metriky: Počet současných úloh, délka fronty, čekací doba, počet Worker instancí.
Test: Zátěžové scénáře s 1, 3 a 5 současně přijatými e-maily.

NFR-03 – Spolehlivost a obnova
Požadavek: Zajistit obnovu zpracování po dočasné chybě nebo restartu Workeru.
Metriky: Počet failed/retry úloh, stáří nevyřízených úloh.
Test: Simulace chyby Gmail API, Gemini API a restartu Workeru.

NFR-04 – Idempotence
Požadavek: Jedna příchozí zpráva nesmí způsobit více automatických odpovědí.
Metriky: Počet duplicitních událostí a duplicitních odpovědí.
Test: Opakované doručení stejné události, souběžné spuštění úlohy a nejasný výsledek odeslání.

NFR-05 – Bezpečnost
Požadavek: Zabránit neoprávněnému přístupu, úniku dat a nepovoleným akcím AI.
Metriky: Neautorizované požadavky, bezpečnostní chyby, odmítnuté přílohy.
Test: Neplatný OIDC token, prompt injection, neplatný soubor a nepovolený příjemce.

NFR-06 – Izolace konverzací
Požadavek: Conversation History smí používat pouze zprávy patřící do aktuálního Gmail vlákna.
Metriky: Počet případů nesprávně načteného kontextu.
Test: Dvě nezávislá vlákna, navazující komunikace a kontrola oddělení historie.

NFR-07 – Kvalita a správnost AI odpovědí
Požadavek: Odpověď musí vycházet z relevantních informací a nesmí doplňovat nepodložená fakta.
Metriky: Úspěšnost testovacích scénářů, správnost RAG retrieval a relevance použitých zdrojů.
Test: Dotazy na znalostní dokumenty, aktuální webová data a kombinované otázky.

NFR-08 – Pozorovatelnost
Požadavek: Každou úlohu musí být možné diagnostikovat pomocí job_id bez logování citlivého obsahu.
Metriky: Latence, chybovost API, počet retry, spotřeba tokenů a provozní náklady.
Test: Kontrola strukturovaných logů a metrik Cloud Monitoring.

NFR-09 – Nákladová efektivita
Požadavek: Omezovat náklady na AI inference, databázi a cloudovou infrastrukturu.
Metriky: Cena za zpracovaný e-mail, tokeny na e-mail, vytížení Cloud Run a Cloud SQL.
Test: Vyhodnocení nákladů při běžném provozu a definované testovací zátěži.

NFR-10 – Udržovatelnost
Požadavek: Používat Modular Monolith a Ports & Adapters pro oddělení aplikační logiky od externích služeb.
Metriky: Úspěšnost automatických testů a rozsah změn při přidání modulu.
Test: Jednotkové a integrační testy modulů Conversation History, RAG a Web Search.

Všechny NFR budou ověřeny během integračních, bezpečnostních a end-to-end testů. Výsledky budou evidovány jako důkaz splnění požadavků.

### Jaká architektonická omezení jsou nezměnitelná?

- ID: constraints (doplňkové)
- Stav: **PŘEDPOKLAD**
- Vlastník: Vývojář
- Zdroj / důkaz: můj návrh

Architektonická omezení projektu Reply McFly:

1. Cloud platforma:
- Nasazení na Google Cloud Platform (GCP) v rámci trial/free-tier prostředí.
- Výchozí region europe-west1 (Belgie), dostupnost služeb a datovou lokalitu je nutné ověřit.
- Veřejný cloud je povinný; GCP je potvrzená projektová volba.

2. Architektonický styl:
- Event-driven Modular Monolith + Ports & Adapters.
- Dvě Cloud Run služby (Ingress a Worker) ze stejného Docker image.
- Asynchronní zpracování přes Pub/Sub a Cloud Tasks.
- Bez Kubernetes, GKE a zbytečných mikroslužeb.

3. Technologie, frameworky a SDK:

- Python 3.12+ – implementační jazyk.
- FastAPI + Uvicorn – HTTP API pro Cloud Run Ingress a Worker.
- Pydantic – validace dat, konfigurace a strukturovaných AI výstupů.
- Google Gen AI SDK (google-genai) – komunikace s Gemini přes Vertex AI, multimodální zpracování, embeddingy a Google Search grounding.
- Google API Python Client + Google Auth – Gmail API, OAuth 2.0, čtení zpráv a historie vláken.
- Google Cloud SDK klientské knihovny – Pub/Sub, Cloud Tasks, Secret Manager a Cloud SQL integrace.
- SQLAlchemy + psycopg 3 – přístup k PostgreSQL.
- Alembic – databázové migrace.
- pgvector – ukládání a vyhledávání RAG embeddingů v PostgreSQL.
- PyMuPDF – validace a zpracování PDF.
- Pillow – validace a zpracování JPEG/PNG.
- FFmpeg/ffprobe – kontrola délky a technických parametrů MP3/WAV.
- pytest – automatizované jednotkové a integrační testy.
- Docker + Docker Compose – kontejnerizace a lokální vývoj.

AI orchestrace:
- Vlastní deterministický EmailOrchestrator implementovaný v Pythonu.
- Samostatné moduly Conversation History, RAG a Web Search.
- LangChain, LangGraph a Google ADK nejsou pro počáteční implementaci vyžadovány.
- Případné zavedení agent frameworku bude zdůvodněno samostatným ADR.

Verze závislostí budou uzamčeny v projektu. Před nasazením ověříme kompatibilitu SDK, Gemini modelu, regionu a dostupných API.

4. Funkční omezení:
- Automatické zpracování nových nepřečtených e-mailů.
- Podpora PDF, MP3, WAV, JPEG a PNG.
- Odpověď ve stejném Gmail vlákně.
- Conversation History, RAG a Live Web Search jsou součástí cílového rozsahu.
- Celková doba od přijetí e-mailu po odeslání odpovědi musí být pod 120 sekund.

5. Bezpečnost a síť:
- Autentizované Cloud Run endpointy (IAM/OIDC).
- Minimální oprávnění servisních účtů.
- OAuth tokeny a secrets mimo zdrojový kód.
- Databáze bez veřejného přístupu.
- Šifrovaná komunikace přes TLS.
- Žádné předávání soukromého obsahu e-mailů do veřejného webového vyhledávání.
- Ochrana proti duplicitním odpovědím a prompt injection.

6. Škálování a provoz:
- Cloud Run autoscaling a řízení souběžnosti pomocí Cloud Tasks.
- Persistentní stav zpracování v PostgreSQL.
- Kontrolované retry a recovery.
- Monitoring latence, chybovosti a nákladů.
- Bez garance neomezeného škálování; kapacita závisí na databázi a API kvótách.

7. Licence a náklady:
- Použití služeb a knihoven s licencemi kompatibilními s projektem.
- Dodržení podmínek Gmail API, Vertex AI a dalších Google Cloud služeb.
- Kontrola provozních nákladů a rozpočtové výstrahy.
- Konkrétní licenční omezení dosud nebyla samostatně posouzena.

Změna potvrzeného technologického řešení vyžaduje zdokumentované architektonické rozhodnutí (ADR). Výchozí provozní parametry, limity instancí a region nejsou nezměnitelné a lze je upravit na základě testů.

## 05 · High Level Design / C4 architektura

*Cíl:* Rozhodni hranice, zodpovědnosti a komunikaci bez přidávání zbytečné složitosti.

*Gate:* Každý box i šipka má zdůvodnění, odpovědnost a failure path.

### Co je uvnitř produktu a co patří externím systémům?

- ID: system_boundary (povinné)
- Stav: **PŘEDPOKLAD**

Hranici systému Reply McFly tvoří vlastní aplikační logika, její cloudová infrastruktura a spravovaná databáze v GCP.

UVNITŘ SYSTÉMU:
- Cloud Run Ingress – příjem a validace událostí.
- Cloud Run Worker – synchronizace a zpracování e-mailů.
- Cloud Tasks – synchronizační a zpracovatelská fronta.
- Cloud SQL PostgreSQL/pgvector – stav úloh, deduplikace, outbox a RAG.
- EmailOrchestrator – řízení AI workflow.
- Attachment Validator – kontrola PDF, MP3, WAV, JPEG a PNG.
- Conversation History, RAG a Web Search moduly.
- Reply Policy – kontrola a bezpečné odesílání odpovědí.
- Cloud Scheduler, Secret Manager a Cloud Monitoring.
- Vlastní zdrojový kód, konfigurace a testy.

EXTERNÍ SYSTÉMY:
- Gmail / Gmail API – e-mailová schránka, historie vláken a doručování zpráv.
- Vertex AI Gemini – externě poskytované LLM inference a embeddingy.
- Google Search grounding – získávání aktuálních veřejných informací.
- Odesílatelé e-mailů – externí uživatelé systému.

Hranice odpovědnosti:
- Aplikace řídí zpracování, bezpečnostní pravidla, výběr kontextu a odeslání odpovědi.
- Gmail zajišťuje správu schránky a doručování.
- Vertex AI poskytuje AI modely.
- Google Search poskytuje aktuální veřejná data.
- Správu infrastruktury GCP zajišťuje poskytovatel cloudu, zatímco za konfiguraci a aplikační logiku odpovídá projekt.

Externí služby se integrují prostřednictvím definovaných adaptérů. AI model nemá přímá oprávnění k odesílání e-mailů.

### Jaký architektonický styl volíš a proč?

- ID: architecture_style (povinné)
- Stav: **PŘEDPOKLAD**

Zvolený styl: Event-driven Modular Monolith + Ports & Adapters, nasazený jako serverless aplikace na Google Cloud Platform.

Event-driven:
- Gmail Watch a Pub/Sub spouštějí zpracování nových zpráv.
- Cloud Tasks odděluje příjem událostí od AI zpracování.
- Fronty umožňují řídit souběžnost, retry a zatížení systému.

Modular Monolith:
- Jedna aplikace obsahuje nezávislé funkční moduly.
- Dvě Cloud Run služby (Ingress a Worker) používají stejný repozitář a Docker image.
- Conversation History, RAG a Web Search nejsou samostatné mikroslužby.
- Snižuje se počet nasazovaných komponent a provozní složitost.

Ports & Adapters:
- Business logika je oddělena od Gmail API, Gemini, PostgreSQL a cloudových SDK.
- Externí integrace lze měnit prostřednictvím adaptérů.
- Moduly lze samostatně testovat pomocí mockovaných rozhraní.

AI orchestrace:
- Vlastní deterministický EmailOrchestrator implementuje WorkflowRunner rozhraní.
- Nové schopnosti lze doplnit jako samostatné moduly.
- Při složitějším workflow lze zavést LangGraph bez nutnosti kompletně přestavět cloudovou infrastrukturu.

Důvody výběru:
- Jednoduchá implementace a obhajitelnost.
- Automatické horizontální škálování aplikační vrstvy.
- Persistentní zpracování a kontrola duplicit.
- Nižší provozní složitost než mikroslužby.
- Rozšiřitelnost bez předčasného zavádění agent frameworku.
- Možnost optimalizace latence pod 120 sekund.

### Vyjmenuj komponenty, jejich jedinečnou odpovědnost a vlastníka.

- ID: components (povinné)
- Stav: **PŘEDPOKLAD**

KOMPONENTY REPLY MCFLY

1. Gmail API + Watch
Odpovědnost: Detekce změn ve schránce, čtení zpráv, historie vláken a odesílání odpovědí.
Vlastník: Google (služba), AI Engineer (integrace).

2. Pub/Sub
Odpovědnost: Doručení Gmail notifikací.
Vlastník konfigurace: Cloud Infrastructure / AI Engineer.

3. Cloud Run Ingress
Odpovědnost: Ověření Pub/Sub notifikace a vytvoření synchronizační úlohy.
Vlastník: Backend / AI Engineer.

4. Cloud Tasks Sync Queue
Odpovědnost: Řízení synchronizace Gmail schránky.
Vlastník: Cloud Infrastructure / AI Engineer.

5. Cloud Run Worker – Sync
Odpovědnost: Gmail History API, filtrování nových zpráv a jejich evidence.
Vlastník: Backend / AI Engineer.

6. Cloud Tasks Process Queue
Odpovědnost: Fronta jednotlivých e-mailových úloh, řízení souběžnosti a retry.
Vlastník: Cloud Infrastructure / AI Engineer.

7. Cloud Run Worker – Process
Odpovědnost: Kompletní zpracování e-mailu a spuštění AI workflow.
Vlastník: Backend / AI Engineer.

8. EmailOrchestrator
Odpovědnost: Výběr kontextu, koordinace AI modulů a generování návrhu odpovědi.
Vlastník: AI Engineer.

9. Attachment Validator
Odpovědnost: Validace a příprava PDF, MP3, WAV, JPEG a PNG.
Vlastník: AI Engineer.

10. Conversation History Provider
Odpovědnost: Načtení relevantních zpráv pouze z aktuálního Gmail vlákna.
Vlastník: AI Engineer.

11. RAG Provider
Odpovědnost: Vyhledávání informací ve znalostní bázi.
Vlastník: AI Engineer.

12. Web Search Provider
Odpovědnost: Získávání aktuálních veřejných informací pomocí Google Search grounding.
Vlastník: AI Engineer.

13. Gemini Adapter
Odpovědnost: Komunikace s Vertex AI Gemini přes Google Gen AI SDK.
Vlastník: AI Engineer.

14. Reply Policy + Gmail Sender
Odpovědnost: Validace odpovědi, příjemce, threading hlaviček a bezpečné odeslání.
Vlastník: Backend / AI Engineer.

15. Cloud SQL PostgreSQL + pgvector
Odpovědnost: Persistentní stav, idempotence, outbox, synchronizace a RAG dokumenty.
Vlastník: Database / AI Engineer.

16. Cloud Scheduler
Odpovědnost: Obnova Gmail Watch a kontrola nedokončených úloh.
Vlastník: Cloud Infrastructure / AI Engineer.

17. Secret Manager
Odpovědnost: Bezpečné uchování OAuth tokenů a konfigurace.
Vlastník: Cloud Infrastructure / AI Engineer.

18. Cloud Logging / Monitoring
Odpovědnost: Diagnostika, metriky, latence a provozní upozornění.
Vlastník: Cloud Infrastructure / AI Engineer.

Poznámka: Ingress a Worker jsou dvě nasazené Cloud Run služby. Sync a Process jsou dvě operace stejné Worker služby. AI moduly jsou součástí jednoho Modular Monolithu, nikoliv samostatné cloudové služby.

V rámci PoC může všechny implementační role zastávat jeden AI Engineer.

### Popiš šipky komponent: kdo → kdo, protokol, sync/async, timeout.

- ID: component_flows (povinné)
- Stav: **PŘEDPOKLAD**

HLAVNÍ TOK ZPRACOVÁNÍ

1. Gmail Watch → Pub/Sub
- Protokol: Google managed event delivery.
- Typ: Asynchronní.
- Účel: Oznámení změny schránky.

2. Pub/Sub → Cloud Run Ingress
- Protokol: HTTPS POST + OIDC.
- Typ: Asynchronní push, synchronní HTTP potvrzení.
- Účel: Předání a ověření notifikace.

3. Ingress → Cloud Tasks Sync Queue
- Protokol: Google Cloud Tasks API přes HTTPS.
- Typ: Synchronní vytvoření asynchronní úlohy.
- Účel: Naplánování synchronizace.

4. Sync Queue → Cloud Run Worker /tasks/sync
- Protokol: HTTPS POST + OIDC.
- Typ: Asynchronní doručení úlohy, synchronní HTTP vykonání.
- Účel: Synchronizace Gmail schránky.

5. Worker Sync → Gmail API
- Protokol: HTTPS REST + OAuth 2.0.
- Typ: Synchronní request/response.
- Účel: history.list a messages.get.

6. Worker Sync ↔ Cloud SQL PostgreSQL
- Protokol: PostgreSQL přes zabezpečené připojení.
- Typ: Synchronní databázové operace.
- Účel: Evidence zpráv a checkpoint.

7. Worker Sync → Cloud Tasks Process Queue
- Protokol: Cloud Tasks API přes HTTPS.
- Typ: Synchronní vytvoření asynchronní úlohy.
- Účel: Zařazení konkrétního e-mailu.

8. Process Queue → Cloud Run Worker /tasks/process
- Protokol: HTTPS POST + OIDC.
- Typ: Asynchronní doručení, synchronní HTTP vykonání.
- Účel: Kompletní AI zpracování.
- Cloud Run request timeout: 110 sekund.
- Aplikační deadline: maximálně 100 sekund.

9. Worker Process → Gmail API
- Protokol: HTTPS REST + OAuth 2.0.
- Typ: Synchronní.
- Účel: Načtení e-mailu, příloh a historie aktuálního vlákna.

10. Worker Process → PostgreSQL/pgvector
- Protokol: PostgreSQL.
- Typ: Synchronní.
- Účel: Stav úlohy, RAG retrieval a outbox.

11. EmailOrchestrator → Vertex AI Gemini
- Protokol: Google Gen AI SDK / HTTPS API.
- Typ: Synchronní volání z pohledu workflow.
- Účel: Multimodální analýza a generování odpovědi.

12. Web Search Provider → Google Search grounding
- Protokol: Vertex AI Gemini API / HTTPS.
- Typ: Synchronní volání.
- Účel: Získání aktuálních veřejných informací bez předání soukromého e-mailového obsahu.

13. Reply Sender → Gmail API
- Protokol: HTTPS REST + OAuth 2.0.
- Typ: Synchronní.
- Účel: Odeslání odpovědi do původního vlákna.

14. Cloud Scheduler → Maintenance workflow
- Protokol: Autentizované cloudové API / HTTPS.
- Typ: Asynchronně plánované spuštění.
- Účel: Obnova Gmail Watch a recovery.

TIMEOUT A RETRY POLITIKA:
- Celkový požadavek: odpověď do 120 sekund od přijetí e-mailu.
- Worker: aplikační deadline 100 sekund, Cloud Run timeout 110 sekund.
- Externí API volání musí mít vlastní timeout a respektovat zbývající časový rozpočet.
- Cloud Tasks používá exponential backoff a omezený počet pokusů.
- Před opakováním odeslání se ověřuje stav v databázi a Gmailu.
- Konkrétní timeouty ostatních API volání budou stanoveny a ověřeny během implementace.

### Jaké aspoň 2 rozumné alternativy jsi zvážil a proč nevyhrály?

- ID: architecture_alternatives (povinné)
- Stav: **PŘEDPOKLAD**

ZVOLENÉ ŘEŠENÍ:
Event-driven Modular Monolith + Ports & Adapters na GCP.

ALTERNATIVA 1 – Microservices Architecture

Návrh:
Samostatné služby pro Gmail synchronizaci, přílohy, Conversation History, RAG, Web Search a AI inference.

Výhody:
- Nezávislý deployment jednotlivých služeb.
- Samostatné škálování každé funkce.
- Vhodné pro větší týmy a komplexní systémy.

Nevýhody:
- Vyšší provozní a implementační složitost.
- Více síťových volání a potenciálně vyšší latence.
- Složitější monitoring, bezpečnost a komunikace mezi službami.
- Vyšší nároky na správu infrastruktury.

Rozhodnutí:
Nezvoleno. Pro PoC s jednou Gmail schránkou a časovým limitem 120 sekund nepřináší dostatečnou hodnotu oproti Modular Monolithu.

ALTERNATIVA 2 – Synchronní aplikace bez front

Návrh:
Jedna Cloud Run služba pravidelně kontroluje Gmail a přímo vykonává celé AI zpracování.

Výhody:
- Jednoduchý počáteční návrh.
- Méně cloudových komponent.
- Snadné vytvoření základního prototypu.

Nevýhody:
- Horší oddělení příjmu zpráv od náročného AI zpracování.
- Složitější řízení souběžnosti a opakovaných pokusů.
- Vyšší riziko ztráty práce při chybě procesu.
- Omezená kontrola přetížení a čekajících úloh.

Rozhodnutí:
Nezvoleno pro cílový cloudový deployment. Cloud Tasks a PostgreSQL poskytují řízené zpracování, evidenci a recovery.

ALTERNATIVA 3 – Agent Framework (LangGraph / CrewAI)

Návrh:
Použít specializovaný framework pro orchestraci AI kroků a nástrojů.

Výhody:
- Podpora podmíněných workflow a složitějšího rozhodování.
- Možnost rozšíření o více agentů.
- Pokročilé řízení stavu AI workflow.

Nevýhody:
- Další závislosti a implementační složitost.
- Potřeba správy a testování stavového modelu frameworku.
- Přínos je omezený při jednoduchém deterministickém workflow.

Rozhodnutí:
Nezvoleno pro první verzi. Použijeme vlastní EmailOrchestrator přes WorkflowRunner rozhraní. Pokud složitost workflow vzroste, můžeme zavést LangGraph.

FINÁLNÍ ZDŮVODNĚNÍ:

Event-driven Modular Monolith poskytuje nejlepší kompromis mezi jednoduchostí, spolehlivostí, škálováním, provozními náklady a možností dalšího rozšiřování.

Architektura umožňuje postupně implementovat Conversation History, RAG a Live Web Search bez nutnosti měnit základní cloudový proces.

### Jaké konkrétní technologie/verze zvolíš pro UI, API, DB, infra a proč?

- ID: tech_stack (povinné)
- Stav: **PŘEDPOKLAD**

TECHNOLOGICKÝ STACK – REPLY MCFLY

1. UI
- Bez samostatného webového UI. Uživatelským rozhraním je Gmail/e-mail.
- Správa a diagnostika přes Google Cloud Console.

2. Backend a API
- Python 3.12 – implementační jazyk (navržená verze).
- FastAPI + Uvicorn – HTTP endpointy Ingress a Worker.
- Pydantic v2 – validace vstupů, konfigurace a strukturovaných odpovědí.
- Google API Python Client + Google Auth – Gmail API, OAuth 2.0 a Gmail Threads API.

3. AI a orchestrace
- Google Gen AI SDK (google-genai) – komunikace s Gemini přes Vertex AI.
- Vlastní EmailOrchestrator s rozhraním WorkflowRunner.
- Samostatné moduly Conversation History, RAG a Web Search.
- LangGraph, LangChain ani CrewAI nejsou v první verzi vyžadovány.
- Architektura umožňuje pozdější nahrazení orchestrace implementací LangGraph.

4. Databáze
- Cloud SQL PostgreSQL – persistentní stav, checkpointy, idempotence a outbox.
- pgvector – ukládání embeddingů a RAG retrieval.
- SQLAlchemy 2.x + psycopg 3 – databázová vrstva.
- Alembic – databázové migrace.

5. Přílohy
- PyMuPDF – kontrola a čtení PDF.
- Pillow – validace JPEG/PNG.
- FFmpeg/ffprobe – kontrola délky a parametrů MP3/WAV.
- Gemini – multimodální interpretace podporovaných příloh.

6. Cloud infrastruktura
- Google Cloud Platform, výchozí region europe-west1.
- Cloud Run – Ingress a Worker.
- Pub/Sub – Gmail Watch notifikace.
- Cloud Tasks – Sync Queue a Process Queue.
- Cloud Scheduler – obnova Gmail Watch a recovery.
- Secret Manager – OAuth tokeny a přístupové údaje.
- Cloud Logging / Monitoring – diagnostika a metriky.
- IAM/OIDC – autentizace mezi službami.

7. Vývoj, deployment a testování
- Docker – jeden image pro Ingress a Worker.
- Docker Compose – lokální vývoj.
- pytest – jednotkové a integrační testy.
- GCP konfigurace verzovaná v repozitáři.

DŮVODY VÝBĚRU:
- Jednoduchý Python stack.
- Nativní integrace s Google Cloud a Gemini.
- Serverless autoscaling.
- Minimální počet samostatných služeb.
- Jedna databáze pro stav aplikace a RAG.
- Modularita a možnost dalšího rozšiřování.

Přesné patch verze, verze PostgreSQL, pgvector a identifikátor Gemini modelu budou uzamčeny až po ověření kompatibility a dostupnosti v GCP projektu.

### Kde jsou hranice důvěry, veřejná síť a citlivá data?

- ID: trust_boundaries (povinné)
- Stav: **PŘEDPOKLAD**

HRANICE DŮVĚRY – REPLY MCFLY

1. Externí odesílatel → Gmail
- E-maily a přílohy jsou nedůvěryhodný vstup.
- Mohou obsahovat škodlivé soubory, neplatná data nebo prompt injection.
- Gmail OAuth omezuje přístup aplikace k dedikované schránce.

2. Gmail / Pub/Sub → Cloud Run Ingress
- Veřejně dosažitelný HTTPS endpoint s povinnou IAM/OIDC autentizací.
- Ověření identity odesílatele, povolené schránky a struktury události.
- Neautorizované požadavky se odmítají.

3. Cloud Tasks → Cloud Run Worker
- Autentizované HTTPS požadavky pomocí servisních identit.
- Pouze oprávněné služby mohou spouštět synchronizaci a zpracování.
- Worker kontroluje identifikátor a stav úlohy v databázi.

4. Worker → Cloud SQL PostgreSQL
- Databáze není veřejně přístupná.
- Přístup je omezen na oprávněné servisní identity a databázové účty.
- Ukládají se pouze nezbytná data pro stav úloh, outbox a RAG.
- Těla e-mailů a přílohy se standardně neukládají trvale.

5. Worker → Vertex AI Gemini
- Externí hranice důvěry mezi aplikací a spravovanou AI službou.
- Předávají se pouze potřebná data, validované přílohy a relevantní kontext.
- Model nesmí rozhodovat o oprávněních, příjemcích ani přímo odesílat e-maily.

6. Worker → Web Search
- Vyhledávání dostává pouze bezpečný veřejný dotaz.
- Soukromé e-maily, přílohy, osobní údaje ani autentizační tokeny se do webových dotazů nepředávají.
- Výsledky webu se považují za nedůvěryhodný obsah.

7. Tajné údaje a monitoring
- OAuth tokeny a secrets jsou uloženy v Secret Manageru.
- Komunikace s API používá TLS.
- Provozní logy neobsahují těla e-mailů, přílohy ani přístupové tokeny.
- Přístup se řídí IAM a principem nejnižších oprávnění.

8. Výstupní bezpečnostní hranice
- Gemini vrací pouze návrh odpovědi.
- Backend provádí validaci obsahu, příjemce a Gmail threading hlaviček.
- Odesílání přes Gmail API řídí výhradně Reply Policy + Sender.

Hlavní princip: Externí obsah je vždy nedůvěryhodný. Bezpečnostní rozhodnutí a oprávnění zůstávají v aplikační logice.

### Kdo vlastní každou komponentu a kdo ji provozuje?

- ID: ownership_boundaries (doplňkové)
- Stav: **PŘEDPOKLAD**

VLASTNICTVÍ A PROVOZ KOMPONENT

Pro PoC zastává role Solution Architect, Backend Engineer, AI Engineer a Cloud Engineer jedna odpovědná osoba.

1. Aplikační komponenty
- Cloud Run Ingress, Worker, EmailOrchestrator, WorkflowRunner a Reply Policy.
- Vlastník: AI Engineer / Solution Architect.
- Provoz: AI Engineer v GCP.
- Odpovědnost: Kód, konfigurace, deployment, bezpečnost a testování.

2. Kontextové a AI moduly
- Attachment Validator, Conversation History, RAG, Web Search a Gemini Adapter.
- Vlastník: AI Engineer.
- Provoz: Součást Cloud Run Workeru.
- Odpovědnost: Správnost zpracování, validace, kontext a kvalita odpovědí.

3. Cloudová infrastruktura
- Cloud Run, Pub/Sub, Cloud Tasks, Cloud Scheduler, Secret Manager a Monitoring.
- Vlastník konfigurace: AI Engineer / Cloud Engineer.
- Provoz infrastruktury: Google Cloud.
- Odpovědnost projektu: IAM, konfigurace, kvóty, monitoring, náklady a incidenty.

4. Databáze a znalostní báze
- Cloud SQL PostgreSQL + pgvector.
- Vlastník datového modelu a aplikace: AI Engineer.
- Správa databázové infrastruktury: Google Cloud.
- Odpovědnost projektu: Migrace, přístupová práva, zálohy, retence a integrita dat.
- Obsah znalostní báze schvaluje vlastník příslušných dokumentů; v PoC AI Engineer.

5. Externí služby
- Gmail API, Vertex AI Gemini a Google Search grounding.
- Poskytovatel a provozovatel: Google.
- Vlastník integrace: AI Engineer.
- Odpovědnost projektu: OAuth, API konfigurace, kvóty, chybové stavy a bezpečné používání.

6. Vývoj a testování
- Docker, Docker Compose, pytest, repozitář a dokumentace.
- Vlastník a provoz: AI Engineer.
- Odpovědnost: Verzování, testy, reprodukovatelnost a deployment.

Odpovědnost za správnost aplikace, bezpečnou konfiguraci a zpracování dat zůstává na straně projektu. Google odpovídá za provoz spravovaných cloudových služeb v rozsahu jejich podmínek.

### Které úlohy musí být async a proč; jaké jsou retry/dedup?

- ID: async_justification (doplňkové)
- Stav: **PŘEDPOKLAD**

ASYNCHRONNÍ ZPRACOVÁNÍ – REPLY MCFLY

1. Gmail Watch → Pub/Sub
- Asynchronní doručení informace o změně schránky.
- Důvod: Oddělení Gmailu od aplikační infrastruktury.

2. Pub/Sub → Ingress → Cloud Tasks Sync Queue
- Ingress ověří notifikaci a zařadí synchronizační úlohu.
- Důvod: Rychlé potvrzení události bez čekání na Gmail synchronizaci.
- Retry: Při dočasné chybě Ingress vrací HTTP 5xx, Pub/Sub doručení opakuje.

3. Cloud Tasks Sync Queue → Worker
- Asynchronní plánování synchronizace schránky.
- Důvod: Kontrola souběžnosti a bezpečné zpracování Gmail History API.
- Limit: Maximálně jedna aktivní synchronizace na schránku.
- Dedup: Databázový lease v mailbox_sync_state.
- Checkpoint historyId se posune až po bezpečné evidenci nalezených zpráv.

4. Worker Sync → Cloud Tasks Process Queue
- Každý nový e-mail dostane samostatnou úlohu.
- Důvod: Paralelní AI zpracování, škálování a izolace chyb.
- Výchozí limit: 3 současně zpracovávané e-maily.
- Retry: Omezené opakování s exponential backoff.
- Dedup: Unikátní kombinace mailbox_id + gmail_message_id.

5. Worker Process → AI workflow
- AI workflow běží uvnitř jedné zpracovatelské úlohy.
- Gmail API, PostgreSQL, RAG, Web Search a Gemini mohou používat asynchronní I/O, ale netvoří samostatné cloudové úlohy.
- Důvod: Nižší orchestrace overhead a snadnější dodržení 120sekundového limitu.
- Jednotlivá externí volání mají vlastní timeouty a respektují celkový deadline.

6. Cloud Scheduler → Maintenance
- Plánované úlohy obnovují Gmail Watch a kontrolují nedokončené zpracování.
- Důvod: Recovery po ztracených notifikacích, chybách a restartech.

RETRY A DEDUP POLITIKA:
- Cloud Tasks používá at-least-once delivery.
- PostgreSQL uchovává stav každé zprávy.
- Worker atomicky rezervuje zpracování pomocí lease s expirací.
- Jedna zpráva nesmí být současně zpracovávána více Workery.
- Outbox eviduje připravenou a odeslanou odpověď.
- Stav SENT vzniká pouze po potvrzení nebo ověření odeslání.
- Při DELIVERY_UNKNOWN se nejdříve kontroluje Gmail.
- Nejasné odeslání se nikdy slepě neopakuje.
- Vlastní a automatické zprávy se filtrují kvůli prevenci e-mailových smyček.
- Více zpráv stejného vlákna musí respektovat pořadí konverzace.

Celkový počet pokusů je výchozím návrhem omezen na 3. Retry nesmí nekontrolovaně překračovat časový rozpočet zpracování.

Asynchronní fronty poskytují spolehlivost a řízení zátěže, ale samy o sobě negarantují odpověď do 120 sekund. Latenci včetně čekání ve frontách je nutné měřit.

### Kde je aktualizovaný C4 context a container diagram?

- ID: architecture_diagram (doplňkové)
- Stav: **PŘEDPOKLAD**

Architektonická dokumentace: Reply McFly – Architektura v1.0, ADR-001, sekce 2 (Finální architektonický diagram).

C4 LEVEL 1 – SYSTEM CONTEXT:
- Uživatel komunikuje s Reply McFly prostřednictvím e-mailu.
- Reply McFly automaticky přijímá a zpracovává zprávy.
- Gmail API poskytuje přístup ke schránce, přílohám a historii vláken.
- Vertex AI Gemini poskytuje multimodální AI inference.
- Google Search grounding poskytuje aktuální veřejné informace.
- Odpověď se odesílá prostřednictvím Gmail API do původního vlákna.

C4 LEVEL 2 – CONTAINER DIAGRAM:
- Cloud Run Ingress – příjem a ověření událostí.
- Pub/Sub – doručování Gmail Watch notifikací.
- Cloud Tasks Sync Queue – plánování synchronizace schránky.
- Cloud Run Worker – synchronizace Gmailu a AI zpracování.
- Cloud Tasks Process Queue – řízení jednotlivých e-mailových úloh.
- Cloud SQL PostgreSQL/pgvector – stav, idempotence, outbox a RAG.
- Vertex AI Gemini – LLM inference a embeddingy.
- Google Search grounding – aktuální veřejná data.
- Cloud Scheduler – Watch renewal a recovery.
- Secret Manager – OAuth tokeny a přístupové údaje.
- Cloud Logging / Monitoring – diagnostika a metriky.

INTERNÍ MODULY WORKERU:
- EmailOrchestrator / WorkflowRunner.
- Attachment Validator.
- Conversation History Provider.
- RAG Provider.
- Web Search Provider.
- Gemini Adapter.
- Reply Policy + Sender.

Diagramy jsou navržené v Mermaid a mají být verzované v repozitáři v adresáři docs/architecture/.

C4 Context a Container diagram budou samostatně vytvořeny a ověřeny proti skutečně nasazené infrastruktuře. Aktuální projektový dokument obsahuje hlavní architektonický diagram, nikoliv ještě formálně oddělené C4 diagramy.


flowchart TD
    U["Uživatel<br/>Odesílatel e-mailu"]
    SYS["Reply McFly<br/>AI Email Assistant"]
    G["Gmail / Gmail API"]
    AI["Vertex AI Gemini"]
    WEB["Google Search Grounding"]

    U -->|"Odesílá e-mail"| G
    G -->|"Notifikace, zprávy, historie"| SYS
    SYS -->|"Odpověď do původního vlákna"| G
    G -->|"Doručuje odpověď"| U
    SYS <-->|"AI inference"| AI
    SYS <-->|"Aktuální veřejné informace"| WEB

    classDef system fill:#dceafa,stroke:#658fbe,color:#23496e
    class SYS system

### Co se škáluje první a jak změříš skutečný bottleneck?

- ID: scaling_strategy (doplňkové)
- Stav: **PŘEDPOKLAD**

STRATEGIE ŠKÁLOVÁNÍ – REPLY MCFLY

Primárně škálujeme Cloud Run Worker, který zpracovává jednotlivé e-maily. Cloud Tasks řídí počet současně spuštěných úloh a chrání databázi i externí API před přetížením.

Výchozí konfigurace:
- Cloud Run Worker: max. 3 instance, concurrency 1.
- Process Queue: max. 3 současné úlohy.
- Sync Queue: max. 1 aktivní synchronizace schránky.
- Cloud Run Ingress: max. 2 instance, concurrency 10.
- Cloud SQL: 1–2 databázová spojení na Worker instanci.

Postup škálování:
1. Změřit end-to-end latenci při 1, 3 a 5 současně přijatých e-mailech.
2. Rozdělit latenci na Gmail detekci, čekání ve frontě, načítání příloh, RAG/Web Search, Gemini a odesílání.
3. Identifikovat komponentu s nejvyšší dobou zpracování nebo čekání.
4. Pokud roste čekání v Process Queue, postupně zvýšit počet Worker instancí a kapacitu fronty.
5. Pokud je bottleneck v Gemini nebo Gmail API, optimalizovat počet volání, velikost kontextu a respektovat API kvóty.
6. Pokud je bottleneck v PostgreSQL, zkontrolovat počet spojení, dobu SQL dotazů a vytížení databáze.

Sledované metriky:
- End-to-end latency: p50, p95 a maximum.
- Délka fronty a stáří nejstarší úlohy.
- Cloud Run instance count, CPU, paměť a concurrency.
- Latence a chybovost Gmail/Gemini API.
- Cloud SQL CPU, počet spojení a latence dotazů.
- Počet HTTP 429, retry a failed jobs.

Škálování musí respektovat požadavek na odpověď pod 120 sekund. Zvýšení počtu instancí samo o sobě nezaručuje splnění limitu při neomezené zátěži.

### Potřebuješ cache? Invalidation, TTL, vlastnictví a dopad selhání.

- ID: cache_decision (doplňkové)
- Stav: **PŘEDPOKLAD**

CACHE STRATEGIE – REPLY MCFLY

Pro počáteční PoC nezavádíme samostatnou distribuovanou cache (Redis/Memorystore).

Důvody:
- Jedna dedikovaná Gmail schránka a omezený počet souběžných úloh.
- Conversation History se načítá z Gmail Threads API.
- RAG dokumenty a embeddingy jsou persistentně uložené v PostgreSQL/pgvector.
- Stav zpracování a deduplikace musí zůstat v transakční databázi.
- Další cache služba by zvýšila složitost a náklady.

Povolené optimalizace:
- Krátkodobé uchování kontextu pouze během zpracování aktuálního e-mailu.
- Opětovné využití již vytvořených embeddingů znalostních dokumentů.
- Omezení opakovaných API volání uvnitř jednoho workflow.
- Načítání pouze relevantních zpráv aktuálního vlákna.

Invalidation:
- Kontext aktuálního e-mailu se po dokončení úlohy zahodí.
- RAG embeddingy se aktualizují při změně verze nebo obsahu dokumentu.
- Gmail historie se mezi zprávami nepovažuje za trvale platnou cache.

TTL:
- Pro dočasný kontext platí životnost jedné zpracovatelské úlohy.
- RAG dokumenty nemají časové TTL; jejich platnost určuje schválená verze dokumentu.

Vlastník:
- AI Engineer / Solution Architect.

Dopad selhání:
- Ztráta dočasného kontextu nesmí ovlivnit persistentní stav úlohy.
- Data lze znovu načíst z Gmail API nebo PostgreSQL.
- Nepoužíváme cache pro idempotenci, outbox ani synchronizační checkpointy.

Pokud testy později prokážou vysokou opakovanou zátěž, vyhodnotíme zavedení cache samostatným ADR.

### Potřebuješ frontu/event bus? Proč nestačí jednoduchý job?

- ID: event_decision (doplňkové)
- Stav: **PŘEDPOKLAD**

EVENT-DRIVEN ARCHITEKTURA – REPLY MCFLY

Ano. Používáme Pub/Sub jako mechanismus doručování událostí a Cloud Tasks jako řízené fronty úloh.

1. Pub/Sub
- Přijímá Gmail Watch notifikace.
- Asynchronně upozorňuje aplikaci na změnu schránky.
- Odděluje Gmail od aplikační infrastruktury.

2. Cloud Tasks Sync Queue
- Plánuje synchronizaci Gmail schránky.
- Omezuje souběžné synchronizace.
- Podporuje opakované doručení při dočasné chybě.

3. Cloud Tasks Process Queue
- Vytváří samostatnou úlohu pro každý nový e-mail.
- Umožňuje paralelní zpracování více e-mailů.
- Řídí concurrency, dispatch rate a retry.
- Odděluje rychlé přijetí události od časově náročného AI workflow.

Proč nestačí jednoduchý synchronní job:
- AI zpracování může trvat desítky sekund.
- Více současných e-mailů vyžaduje řízení kapacity.
- Při chybě Workeru potřebujeme bezpečné opakování.
- Musíme oddělit synchronizaci schránky od zpracování jednotlivých zpráv.
- Potřebujeme monitoring čekajících a neúspěšných úloh.

Proč nepoužíváme složitější event bus:
- Máme jeden hlavní typ vstupní události a definovaný workflow.
- Nepotřebujeme složitou distribuci událostí mezi nezávislými mikroslužbami.
- Pub/Sub + Cloud Tasks pokrývá současné požadavky.

Deduplikace:
- Cloud Tasks negarantuje exactly-once execution.
- PostgreSQL eviduje unikátní identifikátor každé zprávy.
- Worker používá databázové rezervace.
- Outbox zabraňuje nekontrolovanému opakování odesílání.

Zvolený přístup poskytuje jednoduché asynchronní zpracování s kontrolovaným škálováním a obnovou po chybě.

### Kde má být silná nebo eventual konzistence?

- ID: consistency_model (doplňkové)
- Stav: **PŘEDPOKLAD**

KONZISTENČNÍ MODEL – REPLY MCFLY

Používáme kombinaci silné transakční konzistence v PostgreSQL a eventual consistency mezi externími cloudovými službami.

1. Silná konzistence – PostgreSQL
- Unikátní kombinace mailbox_id + gmail_message_id.
- Atomická rezervace email job pomocí databázové transakce.
- Evidence stavu zpracování a expirace lease.
- Bezpečné uložení nalezených zpráv před posunutím Gmail historyId.
- Unikátní vazba outbox záznamu na email job.
- Kontrola přechodů stavů QUEUED, PROCESSING, READY_TO_SEND, SENDING a SENT.
- Zamezení souběžnému vlastnictví stejné úlohy.

2. Eventual consistency – Gmail, Pub/Sub a Cloud Tasks
- Gmail Watch notifikace přicházejí asynchronně.
- Cloud Tasks může doručit úlohu opakovaně.
- Změny v Gmailu a interní databázi neprobíhají v jedné distribuované transakci.
- Stav odeslání může být dočasně neznámý.

3. Řešení nekonzistence
- Gmail historyId slouží jako synchronizační checkpoint.
- Neplatný checkpoint vyvolá řízenou úplnou synchronizaci.
- Cloud Scheduler kontroluje nedokončené úlohy.
- Při DELIVERY_UNKNOWN se ověřuje stav odeslání v Gmailu.
- Odeslání se neopakuje bez ověření.
- Zpracování zpráv stejného vlákna musí respektovat pořadí konverzace.

4. RAG konzistence
- Znalostní dokumenty jsou verzované.
- Embeddingy a jejich zdrojové dokumenty musí odpovídat stejné verzi.
- Aktualizace znalostní báze probíhá řízeně.
- Retrieval používá pouze schválené aktivní dokumenty.

Cíl:
Silnou konzistenci vyžadujeme pro databázový stav, deduplikaci a outbox. Eventual consistency připouštíme při doručování událostí a synchronizaci externích systémů, ale řešíme ji idempotencí, kontrolou stavů a recovery.

### Co se stane při výpadku DB, sítě, providera nebo workeru?

- ID: failure_scenarios (doplňkové)
- Stav: **PŘEDPOKLAD**

FAILURE SCENARIOS – REPLY MCFLY

1. Výpadek Cloud SQL PostgreSQL
- Worker nemůže bezpečně rezervovat ani aktualizovat stav úlohy.
- Zpracování se nepokračuje bez persistentního stavu.
- Cloud Tasks opakuje úlohu podle retry politiky.
- Po obnovení databáze Worker ověří aktuální stav a pokračuje.
- Odeslání odpovědi bez bezpečné evidence v outboxu není povoleno.

2. Výpadek sítě nebo Gmail API
- Požadavek může skončit timeoutem nebo dočasnou API chybou.
- Aplikace provede omezený retry s exponential backoff.
- Úloha zůstává evidována v PostgreSQL.
- Při nejasném výsledku Gmail Send přejde do DELIVERY_UNKNOWN.
- Před případným opakováním odeslání se ověří stav v Gmailu.

3. Výpadek Vertex AI Gemini
- Worker zaznamená chybu AI inference.
- Při dočasné chybě použije omezený retry.
- Při nedostupnosti modelu nebo vyčerpání pokusů přejde úloha do FAILED nebo NEEDS_REVIEW.
- Systém neodesílá vymyšlenou odpověď.

4. Výpadek Web Search
- Pokud dotaz vyžaduje aktuální informaci, systém ji nesmí nahradit neověřeným údajem.
- Odpověď explicitně uvede nemožnost ověření nebo bude úloha předána k ruční kontrole.
- Pokud Web Search není relevantní, workflow pokračuje bez něj.

5. Výpadek RAG
- Pokud je interní znalost nezbytná a retrieval selže, systém neodhaduje chybějící fakta.
- Použije definovanou chybovou odpověď nebo NEEDS_REVIEW.
- Pokud RAG není potřebný, pokračuje bez něj.

6. Restart nebo pád Cloud Run Workeru
- Stav úlohy zůstává v PostgreSQL.
- Cloud Tasks může úlohu doručit znovu.
- Databázový lease zabrání souběžnému vlastnictví.
- Po expiraci lease lze bezpečně obnovit zpracování.

7. Duplicitní Gmail/Pub/Sub notifikace
- Unikátní identifikátor zprávy zabrání vytvoření druhého email job.
- Opakované úlohy ověřují stav v databázi.
- Již odeslaná odpověď se neodesílá znovu.

8. Výpadek Gmail Watch nebo ztracená notifikace
- Cloud Scheduler pravidelně obnovuje Gmail Watch.
- Recovery kontroluje poslední Gmail historyId.
- Při neplatném historyId provede řízenou úplnou synchronizaci.

9. Neplatná nebo nebezpečná příloha
- Attachment Validator přílohu odmítne před AI inference.
- Aplikace zaznamená důvod odmítnutí bez ukládání citlivého obsahu do logů.
- Použije bezpečnou odpověď nebo ruční kontrolu.

10. Překročení 120sekundového limitu
- Worker respektuje interní deadline a ukončuje další náročné operace.
- Nezačne nebezpečné odeslání, pokud není dostatek času na kontrolu výsledku.
- Úloha přejde do odpovídajícího chybového nebo recovery stavu.
- Překročení limitu se zaznamená do monitoringu.

ZÁKLADNÍ PRINCIP:
Systém preferuje bezpečné selhání před duplicitní nebo nepodloženou odpovědí. Cloud Tasks zajišťuje opakování úloh, PostgreSQL trvalý stav a Cloud Scheduler obnovu po výpadku.

### Kdo ověřil návrh, kdy a jaké připomínky zůstaly?

- ID: architecture_review (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

## 06 · Data model, databáze a životní cyklus

*Cíl:* Data jsou zdrojem pravdy, ne dodatek ke kódu.

*Gate:* Víme, co ukládáme, jak to měníme, chráníme, migrujeme a mažeme.

### Jaké jsou hlavní entity, atributy, ID a vztahy?

- ID: entities (povinné)
- Stav: **PŘEDPOKLAD**

HLAVNÍ DATOVÉ ENTITY – REPLY MCFLY

1. mailbox_sync_state
- mailbox_id (PK) – identifikátor Gmail schránky.
- history_id – poslední bezpečně synchronizovaný Gmail checkpoint.
- watch_expiration – expirace Gmail Watch.
- lease_until – rezervace synchronizace.
- updated_at – čas poslední aktualizace.
- Vztah: Jedna schránka má více email_jobs.

2. email_jobs
- id (UUID, PK) – interní identifikátor úlohy.
- mailbox_id – vazba na schránku.
- gmail_message_id – ID příchozí Gmail zprávy.
- gmail_thread_id – ID Gmail vlákna.
- received_at – čas přijetí.
- status – stav zpracování.
- attempt_count – počet pokusů.
- lease_until – rezervace zpracování.
- error_code – poslední chyba.
- created_at, updated_at.
- UNIQUE(mailbox_id, gmail_message_id).
- Vztah: Jedna příchozí zpráva má maximálně jeden email_outbox.

3. email_outbox
- id (UUID, PK).
- job_id (FK, UNIQUE) – vazba na email_jobs.
- outbound_message_id – stabilní RFC Message-ID odpovědi.
- recipient – příjemce určený aplikací.
- draft_body – připravená odpověď.
- status – stav odeslání.
- gmail_sent_message_id – ID odeslané Gmail zprávy.
- sent_at – čas odeslání.
- Vztah: 1:0..1 k email_jobs.

4. knowledge_documents
- id (PK) – identifikátor znalostního dokumentu.
- title – název dokumentu.
- version – verze dokumentu.
- checksum – kontrolní součet obsahu.
- status – aktivní/neaktivní dokument.
- updated_at.
- Vztah: Jeden dokument obsahuje více knowledge_chunks.

5. knowledge_chunks
- id (PK).
- document_id (FK) – vazba na knowledge_documents.
- chunk_index – pořadí části dokumentu.
- content – textová znalostní část.
- embedding – vector(N), pgvector.
- source_reference – odkaz na zdroj.
- Vztah: N:1 ke knowledge_documents.

EXTERNÍ IDENTIFIKÁTORY:
- gmail_message_id – identita konkrétní Gmail zprávy.
- gmail_thread_id – identita konverzace.
- history_id – synchronizační checkpoint schránky, nikoliv ID e-mailu.
- RFC Message-ID – identifikátor používaný v e-mailových hlavičkách.

Conversation History se primárně načítá z Gmail Threads API. Nepotřebujeme vlastní tabulku ukládající celou historii konverzací.

RAG dokumenty jsou oddělené od e-mailové historie. Web Search výsledky se standardně trvale neukládají.

### Kdo vlastní pravdivý stav každého typu dat?

- ID: data_owner (povinné)
- Stav: **PŘEDPOKLAD**

ZDROJE PRAVDY – REPLY MCFLY

1. Gmail
- Source of Truth pro původní e-mailové zprávy, přílohy, historii vláken a stav doručených/odeslaných zpráv.
- Gmail threadId a messageId jsou autoritativní externí identifikátory.
- Aplikace nevytváří vlastní nezávislou kopii celé e-mailové historie.

2. Cloud SQL PostgreSQL
- Source of Truth pro interní stav zpracování e-mailů.
- Vlastní email_jobs, mailbox_sync_state a email_outbox.
- Eviduje checkpointy, deduplikaci, lease, retry a stav odesílání.
- Databázové operace používají transakce.

3. Znalostní dokumenty a RAG
- Schválené znalostní dokumenty představují autoritativní zdroj produktových informací.
- PostgreSQL uchovává jejich verze, textové části a embeddingy.
- Embeddingy jsou odvozená data, nikoliv primární zdroj pravdy.
- Při změně dokumentu se příslušné embeddingy aktualizují.

4. Vertex AI Gemini
- Poskytuje interpretaci obsahu a návrh odpovědi.
- Není Source of Truth pro stav aplikace ani interní fakta.
- Nesmí rozhodovat o autorizaci, příjemci nebo odeslání zprávy.

5. Live Web Search
- Externí veřejné zdroje poskytují aktuální informace.
- Výsledky mají časovou platnost a musí být ověřeny podle zdroje a data.
- Nejsou autoritativní pro interní produktová data.

6. Cloud Tasks a Pub/Sub
- Zajišťují doručování událostí a úloh.
- Nejsou Source of Truth pro zpracování e-mailu.
- Persistentní stav úlohy zůstává v PostgreSQL.

7. Secret Manager
- Source of Truth pro uložené OAuth tokeny a tajné konfigurace.

PRINCIP:
Gmail vlastní e-mailová data, PostgreSQL vlastní interní stav zpracování a schválené dokumenty poskytují znalostní fakta. AI generuje odpovědi, ale není autoritativním datovým úložištěm.

### Jaký DB/úložiště zvolíš a proč?

- ID: database_choice (povinné)
- Stav: **PŘEDPOKLAD**

ZVOLENÁ DATABÁZE:
Google Cloud SQL for PostgreSQL s rozšířením pgvector.

Účel:
- Persistentní evidence zpracování příchozích e-mailů.
- Gmail synchronizační checkpointy.
- Idempotence a prevence duplicit.
- Transakční rezervace úloh.
- Outbox a evidence odeslaných odpovědí.
- RAG dokumenty, textové části a embeddingy.

Důvody výběru PostgreSQL:
1. ACID transakce pro bezpečné změny stavů.
2. UNIQUE constraints pro deduplikaci zpráv.
3. Relační vazby mezi úlohami a odeslanými odpověďmi.
4. Podpora pgvector pro vektorové vyhledávání.
5. Spravovaná služba Cloud SQL v GCP.
6. Kompatibilita s Python, SQLAlchemy a psycopg.
7. Možnost rozšiřování bez dalšího databázového systému.

RAG:
- Pro 1–3 dokumenty používáme jednoduché přesné vektorové vyhledávání.
- Samostatný ANN index zatím není potřebný.
- Není nutné provozovat Milvus, Chroma ani další vector database.

Conversation History:
- Historie se načítá přímo z Gmail Threads API.
- PostgreSQL ukládá identifikátory vláken a stav zpracování, nikoliv kompletní historii.

Přílohy:
- Primárním úložištěm zůstává Gmail.
- Worker přílohy zpracovává dočasně.
- Po dokončení zpracování se dočasná data odstraní.
- Samostatný Cloud Storage bucket není pro počáteční PoC nutný.

Omezení:
- Cloud SQL má průběžné náklady i při nízké zátěži.
- Škálování omezuje výkon instance a počet připojení.
- Dostupnost trial instance a podporované verze PostgreSQL/pgvector je nutné ověřit.

### Jaké tabulky/collections a klíčové constrainty zavedeš?

- ID: data_schema (povinné)
- Stav: **PŘEDPOKLAD**

DATABÁZOVÉ SCHÉMA – REPLY MCFLY

1. mailbox_sync_state
- PK: mailbox_id.
- Pole: history_id, watch_expiration, lease_until, updated_at.
- Účel: Evidence Gmail synchronizace.
- Constraint: Jedna aktivní synchronizační rezervace na schránku, řízená atomickou změnou stavu.

2. email_jobs
- PK: id (UUID).
- FK: mailbox_id → mailbox_sync_state.mailbox_id.
- UNIQUE(mailbox_id, gmail_message_id).
- Pole: gmail_thread_id, received_at, status, attempt_count, lease_until, error_code, created_at, updated_at.
- Účel: Evidence každého příchozího e-mailu a jeho zpracování.
- Indexy: status, lease_until, gmail_thread_id.

3. email_outbox
- PK: id (UUID).
- FK: job_id → email_jobs.id.
- UNIQUE(job_id).
- Pole: outbound_message_id, recipient, draft_body, status, gmail_sent_message_id, sent_at.
- Účel: Kontrolované odesílání odpovědí.
- Doporučený constraint: UNIQUE(outbound_message_id).

4. knowledge_documents
- PK: id.
- Pole: title, version, checksum, status, updated_at.
- Účel: Evidence verzovaných znalostních dokumentů.
- Doporučený constraint: UNIQUE(title, version).

5. knowledge_chunks
- PK: id.
- FK: document_id → knowledge_documents.id.
- Pole: chunk_index, content, embedding vector(N), source_reference.
- Účel: RAG retrieval.
- Doporučený constraint: UNIQUE(document_id, chunk_index).

INTEGRITNÍ PRAVIDLA:
- Povinné identifikátory a stavy nesmějí být NULL.
- Stavové přechody jsou řízeny aplikačním stavovým automatem.
- Změny stavů používají databázové transakce.
- Worker používá lease s expirací a atomickou rezervaci.
- Gmail historyId se aktualizuje až po bezpečné evidenci zpráv.
- Zpráva ve stavu SENT se znovu automaticky neodesílá.
- Výsledek nejasného odeslání se eviduje jako DELIVERY_UNKNOWN.
- RAG retrieval používá pouze aktivní schválené dokumenty.

Databázové schéma bude vytvořeno pomocí Alembic migrací. Konkrétní typy polí a indexy budou ověřeny integračními testy.

### Jak budeš měnit schéma bez ztráty dat a s rollback plánem?

- ID: data_migrations (povinné)
- Stav: **PŘEDPOKLAD**

DATABÁZOVÉ MIGRACE – REPLY MCFLY

Použijeme Alembic pro verzování a řízené migrace PostgreSQL schématu.

Postup změny:
1. Každá změna databáze bude samostatná verzovaná migrace v repozitáři.
2. Migrace se nejprve ověří na lokální PostgreSQL databázi v Docker Compose.
3. Před nasazením se vytvoří záloha nebo ověřený obnovovací bod.
4. Migrace se spustí jako samostatný deployment krok před nasazením nové aplikace.
5. Aplikace ověří očekávanou verzi databázového schématu.
6. Po nasazení se provedou integrační a smoke testy.

Strategie změn:
- Preferovat zpětně kompatibilní změny (expand-contract).
- Nejprve přidat nové sloupce nebo tabulky.
- Následně aktualizovat aplikační logiku.
- Staré sloupce odstranit až po ověření přechodu.
- Datové migrace oddělovat od destruktivních změn schématu.

Rollback:
- Při chybě aplikace přednostně vrátit předchozí kompatibilní verzi Cloud Run.
- Pokud je nutná databázová obnova, použít předem připravený backup/PITR podle dostupné konfigurace Cloud SQL.
- Destruktivní změny nevracet automaticky bez kontroly dat.
- Po obnově ověřit integritu email_jobs, email_outbox, mailbox_sync_state a RAG dokumentů.

Bezpečnost:
- Migrace spouští pouze autorizovaná servisní identita.
- Přístupové údaje jsou v Secret Manageru.
- Migrace se nespouštějí automaticky při startu každé Worker instance.

Cíl:
Zabránit ztrátě dat, nekonzistentním stavům a duplicitním odpovědím při aktualizaci aplikace.

### Co se zálohuje, jak často, kam a jak ověříš obnovení?

- ID: data_backup (povinné)
- Stav: **PŘEDPOKLAD**

ZÁLOHOVÁNÍ A OBNOVA – REPLY MCFLY

1. Cloud SQL PostgreSQL
Zálohovaná data:
- mailbox_sync_state – synchronizační checkpointy.
- email_jobs – stav zpracování zpráv.
- email_outbox – evidence připravených a odeslaných odpovědí.
- knowledge_documents – znalostní dokumenty.
- knowledge_chunks – textové části a embeddingy.

Navržená frekvence:
- Automatická denní záloha Cloud SQL.
- Point-in-Time Recovery (PITR), pokud je podporována a aktivována v konkrétní instanci.
- Dodatečná záloha před rizikovou databázovou migrací.

Umístění:
- Spravované zálohy Google Cloud SQL.
- Lokalita záloh podle konfigurace Cloud SQL a požadavků na umístění dat.

2. Gmail
- Gmail zůstává primárním úložištěm e-mailů a příloh.
- Aplikace nevytváří vlastní úplné zálohy Gmail schránky.
- Při ztrátě synchronizačního checkpointu lze provést řízenou opětovnou synchronizaci dostupných zpráv.

3. RAG dokumenty
- Verzované dokumenty a embeddingy jsou uložené v PostgreSQL.
- Zdrojové dokumenty se uchovávají v řízeném projektovém úložišti.
- Embeddingy lze znovu vytvořit ze schválených zdrojových dokumentů.

4. Konfigurace a zdrojový kód
- Zdrojový kód, databázové migrace a infrastruktura jsou verzované v Git repozitáři.
- OAuth tokeny a secrets jsou v Secret Manageru.
- Obnova secrets a OAuth autorizace se řeší samostatným provozním postupem.

5. Test obnovy
- Obnovit databázi ze zálohy do odděleného testovacího prostředí.
- Ověřit tabulky, vazby, constraints a integritu dat.
- Zkontrolovat stavy email_jobs a email_outbox.
- Ověřit Gmail synchronizaci a RAG retrieval.
- Simulovat přerušenou úlohu a její bezpečné obnovení.
- Potvrdit, že obnova nezpůsobila duplicitní odpověď.

6. RPO / RTO
- Konkrétní cíle RPO a RTO zatím nejsou stanoveny.
- Budou určeny podle dostupnosti záloh, PITR a výsledků recovery testů.
- Obnova po havárii nemusí splnit běžný 120sekundový limit pro odpověď.

Zálohování a restore nejsou zatím ověřené. Před produkčním použitím je nutné úspěšně provést minimálně jeden kompletní test obnovy.

### Jak proběhne výmaz účtu/dat včetně kopií a expirací?

- ID: data_deletion (povinné)
- Stav: **PŘEDPOKLAD**

MAZÁNÍ DAT A RETENCE – REPLY MCFLY

Aplikace používá jednu dedikovanou Gmail schránku a nemá vlastní uživatelské účty. Výmaz se proto vztahuje na e-mailová data, provozní záznamy, znalostní dokumenty a přístupové údaje.

1. E-maily a přílohy
- Primárním úložištěm zpráv a příloh zůstává Gmail.
- Aplikace standardně neukládá celé e-maily ani přílohy trvale do PostgreSQL.
- Dočasně zpracované přílohy se odstraní po dokončení úlohy.
- Výmaz původních zpráv v Gmailu se řeší samostatně podle retenční politiky schránky.

2. PostgreSQL
- email_jobs: metadata a stavy zpracování.
- email_outbox: metadata odeslání a případný draft_body.
- mailbox_sync_state: synchronizační checkpointy.
- knowledge_documents a knowledge_chunks: RAG znalosti a embeddingy.
- Mazání musí respektovat databázové vazby a integritu dat.

3. Retence – návrh pro PoC
- Dočasné přílohy: odstranit bezprostředně po zpracování.
- Outbox draft_body: odstranit po potvrzeném odeslání a uplynutí potřebné kontrolní doby.
- Provozní metadata: navržená retence 30 dní.
- RAG dokumenty: uchovávat po dobu jejich schválené platnosti.
- Cloud Logging: nastavit omezenou retenci a neukládat citlivý obsah.

4. Zálohy
- Odstraněná data mohou zůstat v existujících databázových zálohách do konce jejich retenční doby.
- Zálohy expirují podle nastavení Cloud SQL.
- Po případné obnově starší zálohy musí aplikace znovu aplikovat relevantní požadavky na výmaz.

5. Ukončení provozu
- Zastavit Gmail Watch a zpracovatelské úlohy.
- Zrušit OAuth autorizaci a deaktivovat přístupové údaje.
- Odstranit aplikační data, databázi a cloudové prostředky podle schváleného postupu.
- Ověřit zrušení přístupů a expiraci zbývajících kopií.

6. Ověření
- Zkontrolovat odstranění dat z aktivních úložišť.
- Ověřit referenční integritu.
- Evidovat provedení výmazu bez ukládání citlivého obsahu.

Konkrétní retenční doby a postup právně požadovaného výmazu musí být potvrzeny před produkčním provozem.

### Kde je ERD (vztahy, kardinality, unikátnost)?

- ID: erd_diagram (doplňkové)
- Stav: **PŘEDPOKLAD**

ERD – REPLY MCFLY

Zdroj: Reply McFly – Architektura v1.0, sekce 4.3 (Databázový model).

Navržené umístění diagramu:
docs/architecture/erd.md

Databázový model obsahuje pět hlavních tabulek:

1. mailbox_sync_state
- PK: mailbox_id.
- Vztah 1:N k email_jobs.

2. email_jobs
- PK: id (UUID).
- FK: mailbox_id → mailbox_sync_state.mailbox_id.
- UNIQUE(mailbox_id, gmail_message_id).
- Vztah 1:0..1 k email_outbox.

3. email_outbox
- PK: id (UUID).
- FK: job_id → email_jobs.id.
- UNIQUE(job_id).
- Jeden job smí mít maximálně jeden outbox záznam.

4. knowledge_documents
- PK: id.
- Vztah 1:N ke knowledge_chunks.
- Doporučená unikátnost: (title, version).

5. knowledge_chunks
- PK: id.
- FK: document_id → knowledge_documents.id.
- Doporučená unikátnost: (document_id, chunk_index).
- Embedding: vector(N) pomocí pgvector.

Conversation History:
- Gmail threadId se ukládá do email_jobs.
- Obsah předchozích zpráv se načítá z Gmail Threads API.
- Samostatná tabulka historie konverzací není potřeba.

RAG:
- Znalostní dokumenty a jejich části jsou oddělené od e-mailových úloh.
- Web Search výsledky nejsou standardně trvale ukládány.

ERD je součástí plánované architektonické dokumentace. Musí být ověřeno proti skutečným SQL migracím.

### Jaké indexy vycházejí z reálných dotazů a objemu dat?

- ID: index_strategy (doplňkové)
- Stav: **PŘEDPOKLAD**

INDEX STRATEGIE – POSTGRESQL / PGVECTOR

Indexy navrhujeme podle hlavních přístupových vzorců, nikoliv plošně na všechny sloupce.

1. email_jobs
- UNIQUE(mailbox_id, gmail_message_id).
  Účel: Deduplikace příchozích zpráv a rychlé vyhledání existující úlohy.

- INDEX(status, lease_until).
  Účel: Vyhledání čekajících a přerušených úloh pro retry/recovery.

- INDEX(mailbox_id, gmail_thread_id, received_at).
  Účel: Dohledání zpracovaných zpráv konkrétního vlákna a kontrola jejich pořadí.

2. email_outbox
- UNIQUE(job_id).
  Účel: Maximálně jeden outbox záznam na email job.

- UNIQUE(outbound_message_id).
  Účel: Evidence stabilního RFC Message-ID pro kontrolu odeslání.

- Doporučený index na status a sent_at pouze při prokázané potřebě recovery dotazů.

3. mailbox_sync_state
- PRIMARY KEY(mailbox_id).
  Účel: Rychlé načtení checkpointu jedné schránky.
- Další indexy nejsou pro jednu dedikovanou schránku potřebné.

4. knowledge_documents
- PRIMARY KEY(id).
- Doporučený UNIQUE(title, version).
- Účel: Evidence verzí a kontrola aktivních znalostních dokumentů.

5. knowledge_chunks
- INDEX(document_id, chunk_index), případně UNIQUE.
- Účel: Načtení částí dokumentu ve správném pořadí.
- pgvector umožňuje výpočet podobnosti embeddingů.
- Pro 1–3 dokumenty používáme přesné vektorové vyhledávání bez ANN indexu.
- HNSW/IVFFlat zavedeme pouze při prokázané potřebě většího RAG indexu.

Optimalizace:
- Indexy ověříme pomocí EXPLAIN ANALYZE.
- Budeme sledovat latenci dotazů a velikost tabulek.
- Nepotřebné indexy nebudeme vytvářet kvůli režii zápisů.

Výchozí indexy jsou návrhem. Jejich skutečnou účinnost ověříme na testovacích datech a typických dotazech.

diagram:

erDiagram
    mailbox_sync_state ||--o{ email_jobs : "eviduje"
    email_jobs ||--o| email_outbox : "vytvari"
    knowledge_documents ||--o{ knowledge_chunks : "obsahuje"

    mailbox_sync_state {
        string mailbox_id PK
        string history_id
        timestamp watch_expiration
        timestamp lease_until
        timestamp updated_at
    }
    email_jobs {
        uuid id PK
        string mailbox_id FK
        string gmail_message_id UK
        string gmail_thread_id
        timestamp received_at
        string status
        int attempt_count
        timestamp lease_until
        string error_code
    }
    email_outbox {
        uuid id PK
        uuid job_id FK,UK
        string outbound_message_id
        string recipient
        text draft_body
        string status
        string gmail_sent_message_id
        timestamp sent_at
    }
    knowledge_documents {
        uuid id PK
        string title
        string version
        string checksum
        string status
    }
    knowledge_chunks {
        uuid id PK
        uuid document_id FK
        int chunk_index
        text content
        vector embedding
        string source_reference
    }

### Jaké jsou nejčastější čtecí/zapisovací operace?

- ID: query_patterns (doplňkové)
- Stav: **PŘEDPOKLAD**

HLAVNÍ QUERY PATTERNS – REPLY MCFLY

1. Gmail synchronizace
READ:
- Načtení history_id a lease_until podle mailbox_id.
WRITE:
- Rezervace synchronizace.
- Registrace nových zpráv do email_jobs.
- Aktualizace history_id po bezpečné evidenci zpráv.

2. Deduplikace e-mailů
READ/WRITE:
- INSERT email_jobs s UNIQUE(mailbox_id, gmail_message_id).
- ON CONFLICT DO NOTHING při duplicitní zprávě.
- Kontrola aktuálního stavu existující úlohy.

3. Zpracování e-mailu
READ:
- Načtení email_jobs podle id.
WRITE:
- Atomická rezervace úlohy.
- Změny status, attempt_count a lease_until.
- Uložení chybového stavu při selhání.

4. Conversation History
READ:
- Načtení historie pomocí Gmail Threads API.
- V PostgreSQL případně vyhledání interních email_jobs stejného threadId.
- Historie nesouvisejících vláken se nenačítá.

5. RAG retrieval
READ:
- Výběr aktivních knowledge_documents.
- Vyhledání nejpodobnějších knowledge_chunks podle embeddingu dotazu.
WRITE:
- Import dokumentů, vytvoření chunks a jejich embeddingů.
- Aktualizace při změně verze dokumentu.

6. Odesílání odpovědi
READ:
- Kontrola existujícího outbox záznamu.
WRITE:
- Vytvoření email_outbox.
- Přechod READY_TO_SEND → SENDING → SENT.
- Uložení gmail_sent_message_id a sent_at.

7. Recovery a monitoring
READ:
- Vyhledání RETRY_PENDING a expirovaných PROCESSING úloh.
- Kontrola DELIVERY_UNKNOWN.
- Agregace počtu úloh podle status.
WRITE:
- Aktualizace stavu po retry, recovery nebo ruční kontrole.

Charakter zátěže:
- Časté malé transakční zápisy do email_jobs a email_outbox.
- Krátké čtecí dotazy podle primárních a unikátních klíčů.
- Příležitostné RAG vektorové dotazy.
- Omezený počet dokumentů a zpráv v rámci PoC.

Databáze není používána pro ukládání kompletní historie e-mailů ani jako dlouhodobé úložiště příloh.

### Kde jsou hranice transakcí a co se stane při výpadku uprostřed?

- ID: transaction_boundaries (doplňkové)
- Stav: **PŘEDPOKLAD**

TRANSAKČNÍ HRANICE – REPLY MCFLY

Používáme krátké PostgreSQL transakce. Externí Gmail, Gemini a Cloud Tasks API nejsou součástí databázové transakce.

1. Gmail synchronizace
- Atomicky rezervovat synchronizaci jedné schránky.
- Načíst změny přes Gmail History API mimo databázovou transakci.
- V transakci uložit nově nalezené email_jobs a bezpečný history_id checkpoint.
- Commit až po úspěšné evidenci všech zpráv.
- Po commitu vytvořit Cloud Tasks úlohy.
- Maintenance musí dohledat uložené zprávy, pro které úloha nebyla vytvořena.

2. Rezervace email job
- V krátké transakci ověřit stav a lease.
- Atomicky změnit status na PROCESSING.
- Nastavit lease_until a attempt_count.
- Commit před voláním externích API.
- Při konfliktu druhý Worker úlohu nepřevezme.

3. AI zpracování
- Gmail, RAG retrieval, Web Search a Gemini běží mimo dlouhou DB transakci.
- Výsledek se ukládá samostatnou transakcí.
- Databázové zámky nejsou drženy během AI inference.

4. Outbox
- V jedné transakci uložit připravenou odpověď a stav READY_TO_SEND.
- Odeslání přes Gmail API proběhne mimo databázovou transakci.
- Po potvrzení Gmail Send uložit SENT a gmail_sent_message_id.
- Pokud výsledek nelze určit, přejít do DELIVERY_UNKNOWN.
- Před opakováním odeslání ověřit Gmail.

5. Výpadek uprostřed operace
- Necommitovaná PostgreSQL transakce se vrátí zpět.
- Commitovaná data zůstávají uložená.
- Cloud Tasks může úlohu doručit znovu.
- Worker ověří stav v databázi a bezpečně pokračuje.
- Recovery kontroluje expirované lease a nedokončené úlohy.

ZÁKLADNÍ PRINCIP:
PostgreSQL garantuje atomické změny interního stavu. Externí API se koordinují pomocí idempotence, outboxu a kompenzačních/recovery kroků, nikoliv distribuovanou ACID transakcí.

### Jak řešíš zámky, optimistic locking, race conditions a duplicity?

- ID: concurrency (doplňkové)
- Stav: **PŘEDPOKLAD**

CONCURRENCY A IDEMPOTENCE – REPLY MCFLY

1. Gmail synchronizace
- Jedna aktivní synchronizace na mailbox_id.
- Rezervace pomocí databázového lease_until.
- Atomická aktualizace zabraňuje dvěma Workerům synchronizovat stejnou schránku současně.
- history_id se aktualizuje pouze po bezpečném uložení změn.

2. Email job
- UNIQUE(mailbox_id, gmail_message_id) zabraňuje duplicitní registraci zprávy.
- Worker atomicky rezervuje úlohu pomocí podmíněného UPDATE nebo SELECT FOR UPDATE.
- Lease s expirací umožňuje recovery po pádu procesu.
- Každá změna stavu musí ověřit aktuální status a vlastnictví rezervace.

3. Optimistic concurrency
- Pro změny stavů používáme podmíněné UPDATE a kontrolu počtu změněných řádků.
- Při konfliktu druhý Worker nepokračuje.
- Při potřebě lze doplnit version sloupec.

4. Outbox
- UNIQUE(job_id) zabraňuje vytvoření více outbox záznamů pro stejnou zprávu.
- Stabilní outbound_message_id umožňuje dohledání odpovědi.
- Stav SENT se nikdy automaticky znovu neodesílá.
- DELIVERY_UNKNOWN vyžaduje kontrolu Gmailu před případným opakováním.

5. Pořadí zpráv ve vlákně
- gmail_thread_id identifikuje společnou konverzaci.
- Zprávy stejného vlákna nesmějí být zpracovány v konfliktním pořadí.
- Pro implementaci použijeme databázovou rezervaci na úrovni vlákna nebo ekvivalentní serializační mechanismus.
- Různá vlákna lze zpracovávat paralelně.

6. Cloud Tasks
- At-least-once delivery znamená možné opakované doručení.
- Cloud Tasks není zdrojem pravdy pro idempotenci.
- Skutečný stav je řízen v PostgreSQL.

7. Recovery a race conditions
- Expirovaný lease lze převzít pouze atomicky.
- Zastaralý Worker nesmí přepsat stav nového vlastníka úlohy.
- Před externím odesláním je nutné ověřit oprávnění a aktuální stav.
- Testujeme souběžné spuštění stejné úlohy, restart Workeru a opakované Gmail notifikace.

CÍL:
Paralelně zpracovávat různé e-maily bez duplicit, zachovat pořadí ve stejném vlákně a umožnit bezpečné obnovení po selhání.

### Jak proběhne import, export, změna verze a přenositelnost dat?

- ID: data_import_export (doplňkové)
- Stav: **PŘEDPOKLAD**

IMPORT, EXPORT A PŘENOSITELNOST DAT – REPLY MCFLY

1. Import e-mailů
- Gmail je primárním zdrojem e-mailových dat.
- Worker načítá nové zprávy, přílohy a historii vláken prostřednictvím Gmail API.
- Gmail History API slouží k inkrementální synchronizaci.
- Při neplatném historyId se provede řízená opětovná synchronizace dostupných zpráv.
- E-maily a přílohy se standardně trvale nekopírují do vlastní databáze.

2. Import RAG dokumentů
- Znalostní báze obsahuje 1–3 schválené dokumenty o fiktivním produktu nebo službě.
- Importní proces validuje obsah a vytvoří textové části (chunks).
- Google Gen AI SDK generuje embeddingy přes Vertex AI.
- Dokumenty, jejich verze, části a embeddingy se uloží do PostgreSQL/pgvector.

3. Export dat
- PostgreSQL: export databázového schématu a dat pomocí standardních PostgreSQL nástrojů (např. pg_dump).
- RAG: export zdrojových dokumentů, jejich verzí a metadat.
- Provozní záznamy: export metadat email_jobs a email_outbox podle oprávnění a retenčních pravidel.
- E-mailová data: export prostřednictvím možností Gmailu, odděleně od aplikační databáze.

4. Verzování
- Schéma databáze se verzujeme pomocí Alembic migrací.
- RAG dokumenty mají version a checksum.
- Při změně dokumentu se vytvoří odpovídající nové chunks a embeddingy.
- Používáme pouze schválenou aktivní verzi znalostního dokumentu.

5. Přenositelnost
- Aplikační logika používá Ports & Adapters.
- PostgreSQL využívá standardní SQL a rozšíření pgvector.
- Exportované dokumenty a metadata nejsou závislé na proprietárním formátu vlastní aplikace.
- Gmail a Gemini integrace lze v budoucnu nahradit jinými adaptéry, ale vyžadovalo by to implementaci a testování.

6. Bezpečnost
- Importy a exporty jsou dostupné pouze správci aplikace.
- Přenos dat používá šifrované spojení.
- Export citlivých údajů podléhá přístupovým a retenčním pravidlům.

Konkrétní importní a exportní skripty budou vytvořeny a otestovány během implementace PoC.

### V kterém regionu se data nacházejí a proč?

- ID: data_residency (doplňkové)
- Stav: **PŘEDPOKLAD**

DATA RESIDENCY – REPLY MCFLY

1. Výchozí GCP region
- europe-west1 (Belgie, EU).
- Region je uveden jako výchozí hodnota v projektové konfiguraci.
- Finální region musí být ověřen podle dostupnosti Cloud Run, Cloud SQL, Vertex AI Gemini a dalších používaných služeb.

2. Cloud SQL PostgreSQL
- Databázová instance bude umístěna ve zvoleném EU regionu.
- Uchovává interní stav zpracování, synchronizační checkpointy, outbox a RAG dokumenty.
- Lokalita záloh a případné replikace musí být samostatně nakonfigurována a ověřena.

3. Cloud Run a cloudové fronty
- Cloud Run Ingress a Worker budou nasazeny do europe-west1.
- Cloud Tasks fronty budou vytvořeny ve zvoleném podporovaném EU regionu.
- Pub/Sub a další globálně poskytované služby mají vlastní pravidla umístění dat, která je nutné ověřit.

4. Vertex AI Gemini
- Modely se používají přes Vertex AI.
- Konkrétní region inference musí podporovat vybraný Gemini model a požadované funkce.
- Nelze předpokládat, že všechny modely a Google Search grounding podporují stejné regionální zpracování.
- Pokud nelze požadovanou lokalitu zpracování zajistit, je nutné rozhodnutí přehodnotit před použitím reálných citlivých dat.

5. Gmail
- Gmail je externí spravovaná služba.
- Umístění e-mailových dat se řídí podmínkami a konfigurací poskytovatele.
- Umístění Cloud Run v EU samo o sobě nezaručuje, že všechna Gmail data zůstávají v EU.

6. Bezpečnost a ochrana dat
- Pro PoC používáme syntetická testovací data.
- Přenos mezi službami je šifrovaný.
- Citlivé údaje neodesíláme do veřejného webového vyhledávání.
- Před produkčním provozem ověříme datovou rezidenci, podmínky zpracování a případné přeshraniční přenosy.

DŮVOD VÝBĚRU:
Region europe-west1 je výchozí evropská lokalita projektu. Umožňuje umístit regionální aplikační a databázové komponenty v EU a sjednotit jejich konfiguraci.

Finální umístění dat není dosud technicky ani smluvně ověřeno.

### Jak klasifikuješ data (veřejná, interní, citlivá)?

- ID: data_classification (doplňkové)
- Stav: **PŘEDPOKLAD**

KLASIFIKACE DAT – REPLY MCFLY

Používáme tři základní úrovně klasifikace: PUBLIC, INTERNAL a SENSITIVE.

1. PUBLIC – veřejná data
Příklady:
- Veřejně dostupné informace získané pomocí Google Search grounding.
- Veřejná technická dokumentace.
- Veřejné informace o technologiích a službách.

Pravidla:
- Lze je využít pro odpovědi, pokud je ověřena relevance a aktuálnost.
- Webové výsledky se považují za nedůvěryhodný vstup z hlediska instrukcí.
- Před použitím se ověřují zdroje a datum informace.

2. INTERNAL – interní projektová data
Příklady:
- Architektonická dokumentace.
- Konfigurace bez přístupových údajů.
- Databázové schéma a zdrojový kód.
- Fiktivní RAG znalostní dokumenty.
- Agregované provozní metriky bez osobních údajů.

Pravidla:
- Přístup mají pouze oprávněné servisní identity a správci.
- Dokumenty RAG jsou verzované a schválené.
- Interní informace se neposílají do veřejného Web Search bez schválení.

3. SENSITIVE – citlivá a důvěrná data
Příklady:
- E-mailové adresy a další osobní údaje.
- Těla soukromých e-mailů.
- PDF, MP3, WAV, JPEG a PNG přílohy.
- Historie e-mailových vláken.
- OAuth tokeny, API credentials a secrets.
- Obsah draft_body v email_outbox.
- Provozní metadata, pokud umožňují identifikovat osoby.

Pravidla:
- Přístup podle principu nejnižších oprávnění.
- OAuth tokeny a secrets jsou v Secret Manageru.
- E-maily a přílohy se zpracovávají pouze v nezbytném rozsahu.
- Dočasné přílohy se po zpracování odstraní.
- Obsah e-mailů, přílohy a secrets se nezapisují do provozních logů.
- Soukromá data se neposílají do veřejného webového vyhledávání.
- Před předáním Gemini se kontroluje platnost příloh a bezpečnost vstupu.
- Ukládání a mazání podléhá retenčním pravidlům.

4. Pravidla pro kombinování dat
- Pokud dataset obsahuje osobní nebo citlivé údaje, použije se přísnější klasifikace.
- AI výstup může obsahovat citlivé informace odvozené ze vstupu, proto se před odesláním kontroluje.
- RAG dokumenty a Conversation History zůstávají oddělené kontextové zdroje.
- Externí vyhledávání dostává pouze bezpečně sestavené veřejné dotazy.

KLÍČOVÝ PRINCIP:
Veřejná data lze získávat z webu. Interní a citlivá data se zpřístupňují pouze oprávněným komponentám a nesmějí nekontrolovaně překročit hranice důvěry.

## 07 · API, eventy a externí integrace

*Cíl:* Kontrakty vznikají před implementací a obsahují všechny chyby.

*Gate:* Endpointy mají schéma, autorizaci, chyby, verzování a test.

### Které API endpointy/operace musí vzniknout?

- ID: api_scope (povinné)
- Stav: **PŘEDPOKLAD**

API ROZHRANÍ – REPLY MCFLY

Aplikace používá interní HTTP API implementované pomocí Python/FastAPI. Nemá veřejné uživatelské REST API.

1. Cloud Run Ingress

POST /events/gmail
- Přijímá Gmail Watch notifikace přes Pub/Sub push.
- Ověřuje OIDC identitu, strukturu události a povolenou schránku.
- Vytváří úlohu v Cloud Tasks Sync Queue.
- Vrací HTTP 2xx až po úspěšném vytvoření úlohy.
- Volající: Pub/Sub push servisní identita.

2. Cloud Run Worker

POST /tasks/sync
- Synchronizuje Gmail pomocí history.list.
- Identifikuje nové nepřečtené zprávy.
- Eviduje zprávy v PostgreSQL.
- Vytváří úlohy v Process Queue.
- Volající: Cloud Tasks Sync Queue.

POST /tasks/process
- Přijímá interní identifikátor email job.
- Atomicky rezervuje zpracování.
- Načítá e-mail, přílohy a Conversation History.
- Podle potřeby používá RAG a Live Web Search.
- Volá Vertex AI Gemini.
- Validuje a odesílá odpověď přes Gmail API.
- Ukládá výsledek do PostgreSQL.
- Volající: Cloud Tasks Process Queue.

POST /tasks/maintenance
- Obnovuje Gmail Watch.
- Kontroluje nedokončené úlohy.
- Spouští recovery při ztracených notifikacích.
- Volající: autorizovaný maintenance mechanismus přes Cloud Scheduler.

3. Externí API používaná aplikací

Gmail API:
- users.watch
- users.history.list
- users.messages.get
- users.messages.attachments.get
- users.threads.get
- users.messages.send

Vertex AI Gemini:
- Multimodální AI inference.
- Generování odpovědí.
- Embeddingy pro RAG.
- Google Search grounding pro aktuální informace.

Cloud Tasks API:
- Vytváření a plánování asynchronních úloh.

PostgreSQL:
- Interní databázové operace bez veřejného HTTP endpointu.

Všechny produkční endpointy vyžadují autorizovanou servisní identitu. AI moduly jsou interní Python komponenty, nikoliv samostatná HTTP API.

### Jak vypadají request/response schémata včetně chyb?

- ID: api_contracts (povinné)
- Stav: **PŘEDPOKLAD**

API KONTRAKTY – REPLY MCFLY

Interní API používá HTTPS, JSON a validaci pomocí Pydantic v2.

1. POST /events/gmail

Request:
- Pub/Sub push envelope.
- message.data: Base64-encoded Gmail notifikace.
- Gmail payload: emailAddress, historyId.
- OIDC Bearer token v Authorization hlavičce.

Response:
- HTTP 204 – notifikace přijata a synchronizační úloha bezpečně vytvořena nebo již existuje.
- HTTP 400 – neplatný formát události.
- HTTP 401/403 – neplatná identita nebo nepovolená schránka.
- HTTP 503 – dočasné selhání vytvoření úlohy.

2. POST /tasks/sync

Request:
- mailbox_id: string.
- Interní identifikace úlohy.
- OIDC Bearer token.

Response:
- HTTP 200 – synchronizace dokončena nebo již bezpečně zpracována.
- HTTP 400 – neplatný požadavek.
- HTTP 401/403 – neautorizovaný požadavek.
- HTTP 503 – dočasná chyba Gmail API nebo PostgreSQL.

3. POST /tasks/process

Request:
- job_id: UUID.
- OIDC Bearer token.

Response:
- HTTP 200 – zpracování ukončeno a výsledek bezpečně evidován.
- HTTP 400 – neplatný požadavek.
- HTTP 401/403 – neautorizovaný požadavek.
- HTTP 404 – neexistující email job.
- HTTP 503 – dočasná chyba vyžadující opakování.

4. POST /tasks/maintenance

Request:
- operation: renew_watch | recover_jobs | reconcile_mailbox.
- OIDC Bearer token.

Response:
- HTTP 200 – operace dokončena.
- HTTP 400 – neplatná operace.
- HTTP 401/403 – neautorizovaný požadavek.
- HTTP 503 – dočasná chyba.

DATOVÁ PRAVIDLA:
- Pydantic validuje strukturu všech aplikačních požadavků.
- job_id identifikuje konkrétní interní úlohu.
- mailbox_id identifikuje povolenou Gmail schránku.
- Příjemce odpovědi a Gmail threadId určuje backend z ověřených dat.
- Interní Cloud Tasks požadavky nepřenášejí celé e-maily ani přílohy.
- API nevrací citlivý obsah v chybových odpovědích.

DŮLEŽITÉ:
- Úspěšné HTTP 2xx potvrzuje bezpečné dokončení dané operace, nikoliv nutně odeslání e-mailu.
- Duplicitní nebo již dokončená úloha může vrátit 2xx bez dalšího vykonání.
- Dočasné chyby vracejí 5xx, aby Cloud Tasks nebo Pub/Sub mohly použít retry.
- Stav DELIVERY_UNKNOWN musí být před případným opakováním odeslání zkontrolován.

Přesné JSON schéma, interní chybové kódy a OpenAPI specifikace budou vytvořeny při implementaci FastAPI.

### Jak API ověří identitu a oprávnění pro každou operaci?

- ID: api_auth (povinné)
- Stav: **PŘEDPOKLAD**

API AUTENTIZACE A AUTORIZACE – REPLY MCFLY

1. Cloud Run Ingress – POST /events/gmail
- Příjem pouze autentizovaných Pub/Sub push požadavků.
- OIDC identita ověřovaná přes Cloud Run IAM.
- Přístup pouze pro povolený Pub/Sub push servisní účet.
- Aplikace kontroluje strukturu notifikace a povolenou Gmail schránku.
- Ingress má oprávnění pouze vytvořit synchronizační úlohu.

2. Cloud Run Worker – POST /tasks/sync
- Přístup pouze přes autentizované Cloud Tasks HTTP požadavky.
- Cloud Run kontroluje oprávnění servisní identity.
- Backend ověřuje mailbox_id a stav synchronizace.
- Pouze povolené identity mohou vyvolat synchronizaci.

3. Cloud Run Worker – POST /tasks/process
- OIDC autentizace servisního účtu.
- Backend kontroluje job_id, existenci úlohy a její stav.
- PostgreSQL lease zabraňuje souběžnému zpracování stejné zprávy.
- Volající nesmí určovat libovolného příjemce ani Gmail threadId.

4. Cloud Run Worker – POST /tasks/maintenance
- Přístup pouze pro autorizovanou servisní identitu maintenance workflow.
- Operace jsou omezené na předem definované administrativní úkony.

5. Gmail API
- OAuth 2.0 s offline přístupem pro dedikovanou schránku.
- Používají se minimální potřebná oprávnění, například gmail.readonly a gmail.send.
- OAuth tokeny jsou bezpečně uložené v Secret Manageru.

6. Vertex AI a Google Cloud
- Cloud Run používá vlastní servisní identitu.
- IAM poskytuje přístup pouze k potřebným službám a prostředkům.
- Pro GCP API se preferuje Application Default Credentials.
- Klíče servisních účtů se neukládají do zdrojového kódu.

7. AI bezpečnost
- Gemini nemá přímá oprávnění k Gmail Send ani správě databáze.
- Příjemce a oprávnění určuje aplikace.
- Obsah e-mailů, příloh a webových výsledků nemůže měnit bezpečnostní pravidla.

ZÁKLADNÍ PRINCIP:
Autentizace ověřuje volající službu. Autorizace kontroluje její oprávnění a povolenou operaci. Databázová rezervace následně kontroluje souběžné vlastnictví úlohy.

### Jaká je jednotná chybová obálka a HTTP status kódy?

- ID: api_errors (povinné)
- Stav: **PŘEDPOKLAD**

JEDNOTNÝ MODEL API CHYB – REPLY MCFLY

Interní API používá strukturované JSON chybové odpovědi.

Navržená chybová obálka:

{
  "error": {
    "code": "DEPENDENCY_UNAVAILABLE",
    "message": "Temporary dependency failure",
    "retryable": true,
    "correlation_id": "request-id"
  }
}

POUŽÍVANÉ HTTP STATUS KÓDY:

200 OK
- Operace úspěšně dokončena.
- Také bezpečně rozpoznaná duplicitní nebo již dokončená úloha.

204 No Content
- Událost přijata a bezpečně zařazena bez návratového obsahu.

400 Bad Request
- Neplatný formát nebo chybějící povinná pole.

401 Unauthorized
- Chybějící nebo neplatná autentizace.

403 Forbidden
- Identita nemá oprávnění k operaci nebo schránce.

404 Not Found
- Požadovaný job nebo prostředek neexistuje.

422 Unprocessable Entity
- Neplatná struktura aplikačních dat podle validačního schématu.

429 Too Many Requests
- Překročený aplikační rate limit, pokud bude zaveden.

500 Internal Server Error
- Neočekávaná interní chyba.

503 Service Unavailable
- Dočasná nedostupnost Gmail API, PostgreSQL, Gemini nebo jiné závislosti.

504 Gateway Timeout
- Překročení časového limitu závislosti, pokud odpověď vytváří aplikace.

CHYBOVÉ KÓDY:
- INVALID_REQUEST
- UNAUTHORIZED
- FORBIDDEN
- JOB_NOT_FOUND
- DATABASE_UNAVAILABLE
- GMAIL_API_ERROR
- GEMINI_API_ERROR
- RATE_LIMITED
- DEPENDENCY_TIMEOUT
- DEPENDENCY_UNAVAILABLE
- ATTACHMENT_REJECTED
- DELIVERY_UNKNOWN
- INTERNAL_ERROR

RETRY PRAVIDLA:
- Dočasné chyby vracejí odpovídající 5xx a umožňují retry.
- Neplatné požadavky se neopakují bez opravy.
- Duplicitní doručení není chyba a nevytváří další odpověď.
- Cloud Tasks považuje HTTP 2xx za úspěšné vykonání.
- Trvalá aplikační chyba se uloží do PostgreSQL a zpracování se bezpečně ukončí.

LOGOVÁNÍ:
- Každá chyba obsahuje correlation_id/job_id.
- Logy obsahují technický kód a stav.
- Neobsahují tělo e-mailu, přílohy, OAuth tokeny ani secrets.

Konkrétní mapování aplikačních chyb na HTTP odpovědi bude implementováno a otestováno ve FastAPI.

### Jaké je pravidlo verzování a kompatibility kontraktů?

- ID: api_versioning (povinné)
- Stav: **PŘEDPOKLAD**

API VERSIONING – REPLY MCFLY

Aplikace používá interní HTTP API pro komunikaci mezi Pub/Sub, Cloud Tasks a Cloud Run.

1. Výchozí verze
- Interní kontrakty začínají verzí v1.
- Endpointy zachovávají definované cesty /events/gmail, /tasks/sync, /tasks/process a /tasks/maintenance.
- API schémata budou dokumentována pomocí OpenAPI generovaného FastAPI.

2. Zpětná kompatibilita
- Nová volitelná pole lze přidávat bez změny verze.
- Existující povinná pole se nesmějí bez migrace odstranit nebo přejmenovat.
- Význam existujících stavů a identifikátorů musí zůstat konzistentní.
- Změny request/response schémat vyžadují validační a integrační testy.

3. Breaking changes
- Nekompatibilní změny vyžadují novou verzi kontraktu nebo řízenou migraci.
- Cloud Tasks může obsahovat starší nevyřízené úlohy.
- Nová verze Workeru proto musí po přechodnou dobu zvládat starší podporované payloady.
- Při zásadní změně lze zavést samostatné /v2/ endpointy.

4. Deployment
- Ingress a Worker používají stejný repozitář a Docker image.
- Cloud Run umožňuje nasazování nových revizí.
- Databázové změny používají Alembic a strategii expand-contract.
- Nasazení nové verze nesmí zneplatnit čekající úlohy.

5. Externí API
- Gmail API, Vertex AI a Cloud Tasks mají vlastní verzování poskytovatele.
- Integrace jsou zapouzdřené v adapters.
- Aktualizace SDK nebo modelu vyžaduje regresní testy.

6. Testování
- Test kompatibility starého a nového task payloadu.
- Test zpracování úlohy vytvořené před deploymentem.
- Test databázových migrací a rollbacku.
- Test správného odeslání Gmail odpovědi.

DŮVOD:
Interní API nemá externí zákazníky, ale jeho kontrakty musí zůstat kompatibilní s čekajícími úlohami a nasazenými Cloud Run revizemi.

### Jak fungují list endpointy, cursor/pagination a řazení?

- ID: pagination_convention (doplňkové)
- Stav: **PŘEDPOKLAD**

PAGINATION A ŘAZENÍ – REPLY MCFLY

1. Interní HTTP API
- Aplikace v počátečním PoC nemá veřejné list endpointy.
- Endpointy /events/gmail, /tasks/sync, /tasks/process a /tasks/maintenance vykonávají konkrétní operace.
- Vlastní REST pagination proto není v první verzi potřebná.

2. Gmail History API
- Gmail history.list používá stránkování poskytovatele.
- Worker postupně zpracuje všechny relevantní stránky.
- Pokračovací pageToken je řízen Gmail API.
- Synchronizační historyId se posune až po bezpečném zpracování a evidenci změn.
- Při neplatném historyId se provede řízená opětovná synchronizace.

3. Conversation History
- Historie se načítá pouze pro aktuální gmail_thread_id.
- Zprávy se řadí chronologicky.
- Pro Gemini se vybírá omezený počet relevantních zpráv podle token budgetu.
- Historie jiných vláken se nepřidává.

4. PostgreSQL recovery
- Čekající úlohy lze načítat po omezených dávkách.
- Doporučeno keyset pagination podle stabilního pořadí created_at + id.
- Úlohy se vybírají podle status a lease_until.
- Duplicitní nebo současné převzetí řeší atomická rezervace.

5. RAG retrieval
- Nevyužívá klasické stránkování.
- Vyhledává se omezený počet nejrelevantnějších chunks (Top-K).
- Řazení podle podobnosti embeddingů.
- Výsledek obsahuje identifikátor dokumentu a zdrojovou referenci.

6. Budoucí administrativní API
- Pokud vzniknou list endpointy, použijeme cursor-based pagination.
- Výchozí page_size například 50, maximálně 100.
- Stabilní řazení created_at DESC + id.
- Odpověď bude obsahovat items a next_cursor.
- Parametry a limity se stanoví při implementaci.

PRINCIP:
Nepřidáváme pagination infrastrukturu, kterou současné API nepotřebuje. Používáme nativní Gmail stránkování, omezený retrieval a dávkové zpracování databázových úloh.

### Jaké POST/externí operace musí mít idempotency key?

- ID: api_idempotency (doplňkové)
- Stav: **PŘEDPOKLAD**

IDEMPOTENCE API OPERACÍ – REPLY MCFLY

Idempotenci zajišťuje PostgreSQL pomocí unikátních identifikátorů, atomických rezervací a outboxu.

1. POST /events/gmail
- Idempotentní zpracování opakovaných Pub/Sub notifikací.
- Identifikace podle mailbox_id a Gmail historyId.
- Opakovaná notifikace nesmí způsobit duplicitní odpověď.
- Duplicitní synchronizační požadavky mohou být sloučeny.

2. POST /tasks/sync
- Identifikace podle mailbox_id.
- Jedna aktivní synchronizace na schránku.
- Databázový lease zabraňuje souběžným synchronizacím.
- historyId se aktualizuje až po bezpečném uložení nalezených zpráv.

3. POST /tasks/process
- Idempotency key: mailbox_id + gmail_message_id.
- UNIQUE constraint v tabulce email_jobs.
- Interní job_id jednoznačně identifikuje úlohu.
- Atomická rezervace zabraňuje souběžnému zpracování.
- Zprávy ve stavu SENT se znovu neodesílají.

4. Gmail API – messages.send
- Kritická externí operace s nevratelným vedlejším efektem.
- Používáme email_outbox s UNIQUE(job_id).
- Každá odpověď má stabilní RFC Message-ID.
- Po potvrzení odeslání ukládáme gmail_sent_message_id.
- Při nejasném výsledku přecházíme do DELIVERY_UNKNOWN.
- Před opakováním ověřujeme, zda Gmail již odpověď neodeslal.
- Gmail Send neposkytuje aplikační exactly-once garanci pouze na základě Message-ID.

5. POST /tasks/maintenance
- Opakované spuštění musí být bezpečné.
- Obnova Gmail Watch nesmí přeskočit nezpracované změny.
- Recovery nesmí vytvořit duplicitní email job.

6. RAG import
- Doporučený idempotency key: document_id + version + checksum.
- Opakovaný import stejné verze nesmí vytvářet duplicitní chunks.

PRINCIP:
Cloud Tasks a Pub/Sub mohou doručit událost opakovaně. Idempotence proto musí být v aplikační a databázové vrstvě, nikoliv pouze ve frontě.

### Jaké mají integrace timeouty, retry pravidla a circuit breaker?

- ID: api_timeout_retry (doplňkové)
- Stav: **PŘEDPOKLAD**

TIMEOUT, RETRY A CIRCUIT BREAKER – REPLY MCFLY

Celkový požadavek: odpověď do 120 sekund od přijetí e-mailu.

1. Cloud Run Worker
- HTTP request timeout: 110 sekund.
- Aplikační deadline: maximálně 100 sekund.
- Externí volání nesmějí překročit zbývající časový rozpočet.

2. Gmail API
- Návrhový timeout jednoho volání: 10 sekund.
- Retry při HTTP 429, 500, 502, 503 a 504.
- Exponential backoff s jitter.
- Chyby autorizace a trvale neplatné požadavky se automaticky neopakují.
- Gmail Send má zvláštní pravidla kvůli riziku duplicit.

3. Vertex AI Gemini
- Návrhový timeout inference: maximálně 40 sekund.
- Retry pouze při dočasné chybě a dostatečném zbývajícím deadline.
- Omezit počet pokusů kvůli latenci a nákladům.
- Při selhání nepoužívat vymyšlenou odpověď.

4. RAG / PostgreSQL
- Návrhový timeout databázového dotazu: 5 sekund.
- Krátké transakce a omezený connection pool.
- Retry pouze pro vhodné přechodné chyby.
- Pokud nelze bezpečně rezervovat úlohu, zpracování se nespustí.

5. Web Search
- Návrhový timeout: 15 sekund.
- Pouze při požadavku na aktuální veřejné informace.
- Při nedostupnosti výslovně přiznat, že aktuální fakta nelze ověřit.
- Nepředávat soukromé informace do vyhledávání.

6. Cloud Tasks
- Exponential backoff s omezeným počtem pokusů.
- Výchozí aplikační maximum: 3 pokusy.
- Při přetížení zůstávají úlohy ve frontě.
- Cloud Tasks dispatch deadline musí být kompatibilní s Cloud Run timeoutem.

7. Circuit breaker
- Pro PoC nezavádíme samostatnou circuit breaker infrastrukturu.
- Používáme explicitní timeouty, omezené retry a řízení souběžnosti.
- Při opakovaných chybách externí služby lze dočasně omezit její volání.
- Plnohodnotný circuit breaker doplníme pouze při prokázané potřebě.

8. Ochrana proti opakovanému odeslání
- Odeslání přes Gmail API se nesmí slepě retryovat.
- Při nejasném výsledku uložíme DELIVERY_UNKNOWN.
- Před dalším pokusem se kontroluje stav v Gmailu.

Konkrétní timeouty integrací jsou návrhové hodnoty. Budou upraveny podle měření a skutečných API kvót.

### Jak ověříš webhook podpis, replay a pořadí událostí?

- ID: webhook_security (doplňkové)
- Stav: **PŘEDPOKLAD**

WEBHOOK SECURITY – REPLY MCFLY

Používáme Gmail Watch → Pub/Sub → Cloud Run Ingress.

1. Autentizace webhooku
- Pub/Sub push používá OIDC token servisní identity.
- Cloud Run ověřuje identitu a oprávnění pomocí IAM.
- Přístup má pouze povolená Pub/Sub push identita.
- Aplikace validuje strukturu notifikace a autorizovanou Gmail schránku.
- Nepoužíváme vlastní HMAC podpis, protože ověřujeme Google OIDC identitu.

2. Ochrana proti replay
- Pub/Sub může opakovaně doručit stejnou notifikaci.
- Opakované doručení musí být bezpečné.
- Synchronizace využívá persistentní Gmail historyId checkpoint.
- Databázový lease zabraňuje souběžné synchronizaci stejné schránky.
- Deduplikace konkrétních zpráv používá UNIQUE(mailbox_id, gmail_message_id).

3. Pořadí událostí
- Nepředpokládáme garantované pořadí Pub/Sub notifikací.
- Gmail historyId slouží jako synchronizační checkpoint, nikoliv identifikátor konkrétního e-mailu.
- Worker načítá změny pomocí Gmail History API.
- Checkpoint se posune až po bezpečné evidenci všech nalezených zpráv.
- Při neplatném historyId se provede řízená úplná synchronizace.

4. Potvrzování událostí
- Ingress vrací HTTP 2xx až po úspěšném vytvoření synchronizační úlohy.
- Při dočasné chybě vrací HTTP 5xx pro opakované doručení.
- Neplatné nebo neoprávněné události se odmítají.

5. Bezpečnostní testy
- Chybějící nebo neplatný OIDC token.
- Nepovolená Gmail schránka.
- Neplatný Pub/Sub payload.
- Opakované doručení stejné notifikace.
- Opožděné nebo přeházené notifikace.
- Současné doručení více událostí.

CÍL:
Zajistit, aby webhook spouštěla pouze oprávněná služba a aby opakované nebo opožděné události nezpůsobovaly ztrátu zpráv ani duplicitní odpovědi.

### Jaké externí služby závisí na aplikaci?

- ID: integrations_list (doplňkové)
- Stav: **PŘEDPOKLAD**

EXTERNÍ INTEGRACE – REPLY MCFLY

1. Gmail API
- Účel: Čtení e-mailů, příloh, historie vláken a odesílání odpovědí.
- Kontrakt: Gmail API v1.
- Poskytovatel: Google.
- Vlastník integrace: AI Engineer.
- Autentizace: OAuth 2.0.
- Limity: Gmail API kvóty a limity dedikované schránky.
- Cena: Podle podmínek Gmail služby; přímé API volání není hlavní nákladovou položkou.

2. Vertex AI Gemini
- Účel: Multimodální analýza a generování odpovědí.
- Kontrakt: Google Gen AI SDK a Vertex AI API.
- Poskytovatel: Google Cloud.
- Vlastník integrace: AI Engineer.
- Autentizace: IAM / Application Default Credentials.
- Limity: Kvóty modelu, vstupní/výstupní tokeny, požadavky a dostupnost regionu.
- Cena: Podle použitého Gemini modelu, tokenů a multimodálního obsahu.

3. Vertex AI Embeddings
- Účel: Embeddingy RAG dokumentů a uživatelských dotazů.
- Poskytovatel: Google Cloud.
- Vlastník integrace: AI Engineer.
- Limity: Modelové kvóty, vstupní limity a dimenze embeddingů.
- Cena: Podle použitého embedding modelu a množství zpracovaného obsahu.

4. Google Search Grounding
- Účel: Získávání aktuálních veřejných informací.
- Poskytovatel: Google.
- Vlastník integrace: AI Engineer.
- Kontrakt: Grounding nástroj podporovaný vybraným Gemini modelem.
- Limity: Dostupnost funkce, modelové kvóty a podporované regiony.
- Cena: Podle aktuálního ceníku grounding služby.

5. Google Cloud Tasks
- Účel: Asynchronní synchronizace a zpracování e-mailů.
- Poskytovatel: Google Cloud.
- Vlastník konfigurace: AI Engineer.
- Kontrakt: Cloud Tasks API v2.
- Limity: Dispatch rate, concurrency, retry a kvóty.
- Cena: Podle počtu operací a aktuálního ceníku.

6. Google Cloud Pub/Sub
- Účel: Doručování Gmail Watch notifikací.
- Poskytovatel: Google Cloud.
- Vlastník konfigurace: AI Engineer.
- Limity: Kvóty publikování a doručování zpráv.
- Cena: Podle využití služby.

7. Další spravované služby GCP
- Cloud Run – běh aplikace.
- Cloud SQL – PostgreSQL a pgvector.
- Cloud Scheduler – plánovaná údržba.
- Secret Manager – uchovávání secrets.
- Cloud Logging / Monitoring – diagnostika a metriky.

SPRÁVA KONTRAKTŮ:
- Všechny integrace používají samostatné adaptéry.
- Verze SDK se uzamknou v dependency managementu.
- Aktualizace SDK, API nebo modelu vyžadují regresní testy.
- API kvóty, ceny a dostupnost musí být ověřeny v konkrétním GCP projektu.
- Náklady sledujeme na úrovni jednoho zpracovaného e-mailu.

Konkrétní Gemini model, embedding model, jejich ceny a projektové kvóty zatím nejsou finálně potvrzené.

### Jak otestuješ breaking changes a contract tests?

- ID: contracts_tests (doplňkové)
- Stav: **PŘEDPOKLAD**

API CONTRACT TESTING – REPLY MCFLY

Použijeme pytest, Pydantic, FastAPI TestClient a mockované externí služby.

1. Interní API kontrakty
- Ověřit request/response schémata všech čtyř endpointů.
- Testovat povinná a volitelná pole.
- Testovat neplatné payloady a HTTP statusy.
- Ověřit kompatibilitu starších Cloud Tasks payloadů.
- Porovnávat OpenAPI schéma při změnách API.

2. Gmail API
- Mockovat odpovědi history.list, messages.get, threads.get a messages.send.
- Testovat chybějící nebo neplatné atributy.
- Testovat stránkování a neplatný historyId.
- Ověřit správné Gmail threading hlavičky.

3. Vertex AI Gemini
- Mockovat strukturované AI odpovědi.
- Testovat validní, nevalidní a neúplný výstup.
- Ověřit chování při timeoutu, HTTP 429 a chybě modelu.
- Testovat zpracování multimodálních příloh.

4. RAG a Web Search
- Ověřit formát výsledků retrieval.
- Testovat chybějící dokumenty a neplatné embeddingy.
- Ověřit strukturu výsledků Web Search a dostupnost zdrojů.
- Testovat selhání vyhledávání bez vymýšlení aktuálních informací.

5. Databázové kontrakty
- Testovat Alembic migrace.
- Ověřit primární a cizí klíče.
- Ověřit UNIQUE constraints a transakční chování.
- Testovat souběžnou rezervaci email job.

6. Breaking changes
- Změna povinných polí nebo významu existujících atributů vyžaduje novou verzi kontraktu nebo řízenou migraci.
- CI musí odhalit nekompatibilní změny API schématu.
- Nová verze musí zpracovat podporované starší čekající úlohy.

7. Integrační testy
- Po úspěšných mock testech ověřit reálné Gmail API.
- Ověřit přístup k Vertex AI Gemini.
- Ověřit Pub/Sub → Cloud Tasks → Cloud Run.
- Ověřit celý tok od přijetí e-mailu po odeslání odpovědi.

CÍL:
Zachytit nekompatibilní změny před deploymentem a zajistit, že změna externí integrace neporuší hlavní workflow.

Výsledky testů budou evidovány v CI a technické dokumentaci. Testy dosud nejsou implementovány.

### Jaké limity a ochrany proti zneužití má veřejné API?

- ID: rate_limits_api (doplňkové)
- Stav: **PŘEDPOKLAD**

API RATE LIMITS A OCHRANA PROTI ZNEUŽITÍ – REPLY MCFLY

Aplikace neposkytuje veřejné uživatelské REST API. Cloud Run endpointy jsou dostupné pouze autorizovaným servisním identitám.

1. Autentizace
- Cloud Run vyžaduje IAM/OIDC.
- Pub/Sub push používá autorizovanou servisní identitu.
- Cloud Tasks používá autorizovanou servisní identitu.
- Anonymní přístup není povolen.

2. Cloud Run Ingress
- Max instances: 2.
- Concurrency: 10.
- Validace Pub/Sub notifikací a povolené Gmail schránky.
- Ingress nemá oprávnění k AI inference ani Gmail obsahu.

3. Cloud Run Worker
- Max instances: 3.
- Concurrency: 1.
- Request timeout: 110 sekund.
- Aplikační deadline: maximálně 100 sekund.

4. Cloud Tasks
- Sync Queue: maximálně 1 aktivní synchronizace schránky.
- Process Queue: maximálně 3 současné zpracovatelské úlohy.
- Dispatch rate bude nastaven podle kapacity a externích API kvót.
- Retry používá omezený exponential backoff.

5. Gmail API a Gemini
- Respektování dostupných API kvót.
- Omezený počet opakování při HTTP 429 a dočasných chybách.
- Omezení velikosti kontextu a počtu AI volání.
- Monitoring spotřeby tokenů a nákladů.

6. Ochrana proti zneužití e-mailového vstupu
- Zpracovávají se pouze nové nepřečtené příchozí zprávy.
- Vlastní a známé automatické odpovědi se ignorují.
- Jedna zpráva může vytvořit maximálně jednu automatickou odpověď.
- Přílohy mají limity velikosti, typu, počtu a délky.
- Nedůvěryhodný obsah nemůže změnit oprávnění ani příjemce odpovědi.

7. Ochrana nákladů
- Cloud Run max instances.
- Omezená concurrency.
- Omezený počet AI pokusů.
- Podmíněné spouštění RAG a Web Search.
- GCP rozpočtové výstrahy a monitoring nákladů.

8. Monitoring
- Počet požadavků a odmítnutých volání.
- HTTP 401/403/429/5xx.
- Délka front a stáří čekajících úloh.
- Počet duplicitních zpráv.
- Spotřeba Gemini tokenů a náklady na email job.

Pro počáteční PoC nezavádíme API Gateway ani samostatný WAF. Pokud se aplikace rozšíří o veřejné uživatelské API, bude nutné navrhnout samostatnou ochranu, autentizaci a rate limiting.

Konfigurační limity jsou výchozí návrhové hodnoty a musí být ověřeny zátěžovými testy.

### Existuje sandbox/stub pro každý externí dependency?

- ID: integration_sandbox (doplňkové)
- Stav: **PŘEDPOKLAD**

TESTOVACÍ PROSTŘEDÍ A STUBY – REPLY MCFLY

Pro každou externí závislost bude dostupný testovací stub nebo izolované testovací prostředí. Nevyžadujeme samostatnou sandbox infrastrukturu.

1. Gmail API
- Lokální stub pro Gmail Watch, history.list, messages.get, threads.get a messages.send.
- Testování pomocí syntetických e-mailů a příloh.
- Integrační testy proti dedikované testovací Gmail schránce.
- Ověření správného vlákna, duplicit a chyb API.

2. Vertex AI Gemini
- Mock Gemini Adapteru s předem připravenými strukturovanými odpověďmi.
- Simulace timeoutů, chyb API, neplatného výstupu a překročení kvót.
- Integrační testy proti skutečnému Gemini modelu v GCP trial projektu.

3. RAG a Embeddings
- Lokální PostgreSQL s pgvector přes Docker Compose.
- Testovací znalostní báze s 1–3 fiktivními dokumenty.
- Předem připravené testovací embeddingy nebo mock embedding modelu.
- Integrační test skutečného retrieval a generování embeddingů.

4. Live Web Search
- Stub Web Search Provideru s předem připravenými výsledky a odkazy.
- Simulace prázdných výsledků, zastaralých informací a chyb vyhledávání.
- Integrační test Google Search grounding s veřejným dotazem.
- Soukromá e-mailová data se do vyhledávání nepředávají.

5. Pub/Sub a Cloud Tasks
- Lokální vývojový HTTP adaptér nebo fake queue.
- Simulace duplicitních událostí, retry a opožděného doručení.
- Integrační test skutečného Pub/Sub a Cloud Tasks v GCP.

6. Cloud SQL PostgreSQL
- Lokální PostgreSQL/pgvector v Docker Compose.
- Test databázových migrací, transakcí, lease a UNIQUE constraints.
- Integrační test proti testovací Cloud SQL instanci.

7. Secret Manager a Cloud Scheduler
- Lokální testovací konfigurace bez produkčních přístupových údajů.
- Mock načítání secrets a spouštění maintenance operací.
- Ověření IAM oprávnění a plánovaných úloh v GCP.

TESTOVACÍ STRATEGIE:
- Unit tests: pytest + mockované Ports & Adapters.
- Integration tests: skutečné služby v izolovaném GCP trial prostředí.
- End-to-end tests: odeslání testovacího e-mailu a kontrola automatické odpovědi.
- Failure tests: timeouty, duplicity, nedostupné API a restart Workeru.
- Performance tests: ověření odpovědi pod 120 sekund.

DŮLEŽITÉ:
Stuby slouží pouze pro lokální vývoj a automatizované testy. Produkční Cloud Run používá skutečné adaptéry.

Testovací prostředí a stuby jsou součástí implementačního plánu. Jejich funkčnost zatím nebyla ověřena.

## 08 · Security, identita a ochrana dat

*Cíl:* Chraň uživatele, data, přístupy a infrastrukturu od začátku.

*Gate:* Existuje review identit, autorizace, tajemství, hrozeb a retention.

### Jak bude fungovat registrace, login, reset a MFA/SSO?

- ID: identity_provider (povinné)
- Stav: **PŘEDPOKLAD**

IDENTITY A AUTHENTICATION – REPLY MCFLY

Aplikace nemá vlastní uživatelské účty ani webové přihlašovací rozhraní. Koncoví uživatelé komunikují prostřednictvím e-mailu.

1. Registrace a přihlášení uživatelů
- Registrace a login do Reply McFly nejsou potřeba.
- Uživatelským rozhraním je e-mail.
- Není potřeba implementovat správu hesel ani reset hesla.
- Samostatný Identity Provider, například Firebase Authentication, není vyžadován.

2. Administrátorský přístup
- Správce používá Google Cloud IAM a Google účet.
- Přístup do GCP Console je řízen oprávněními IAM.
- MFA se vyžaduje pro administrátorské účty podle nastavené bezpečnostní politiky.
- SSO lze případně zajistit přes Google Cloud Identity nebo existující organizační identitu.

3. Gmail OAuth 2.0
- Aplikace používá dedikovanou Gmail schránku.
- Správce provede jednorázovou autorizaci Gmail API.
- OAuth refresh token se uloží do Secret Manageru.
- Aplikace používá minimální potřebná Gmail oprávnění.
- Obnovení nebo zrušení autorizace se řeší administrátorským postupem.

4. Service-to-service autentizace
- Pub/Sub a Cloud Tasks používají OIDC servisní identity.
- Cloud Run ověřuje oprávnění přes IAM.
- Worker používá servisní účet pro přístup k GCP službám.
- Servisní účty nepoužívají uživatelská hesla.

5. Bezpečnost
- Žádná vlastní databáze hesel.
- Secrets nejsou ve zdrojovém kódu.
- Anonymní přístup k produkčním Cloud Run endpointům není povolen.

Zvolený přístup využívá Google IAM a OAuth 2.0 místo budování vlastního identity systému.

### Kde se serverově kontroluje přístup k objektům a rolím?

- ID: authorization_policy (povinné)
- Stav: **PŘEDPOKLAD**

AUTHORIZATION POLICY – REPLY MCFLY

Autorizace probíhá ve dvou vrstvách: Google Cloud IAM a aplikační backend.

1. Cloud IAM
- Cloud Run Ingress přijímá pouze autorizované Pub/Sub push požadavky.
- Cloud Run Worker přijímá pouze autorizované Cloud Tasks požadavky.
- Každá servisní identita má pouze nezbytná oprávnění.
- Anonymní volání produkčních endpointů jsou zakázána.

2. Aplikační autorizace – FastAPI
- Každý požadavek musí odpovídat povolené operaci.
- Ingress ověřuje autorizovanou Gmail schránku.
- Worker validuje mailbox_id a job_id.
- Úloha smí pracovat pouze se zprávou evidovanou v databázi.
- Příjemce ani Gmail threadId nesmějí být libovolně určeny volajícím.

3. Databázová autorizace
- PostgreSQL přístup má pouze Worker a autorizované administrativní/migrační operace.
- Databázové účty používají princip nejnižších oprávnění.
- Atomická rezervace kontroluje vlastnictví úlohy.
- UNIQUE constraints chrání před duplicitami.

4. Conversation History
- Historie se načítá výhradně podle aktuálního gmail_thread_id.
- Aplikace nesmí spojovat kontext nesouvisejících vláken.
- Gmail OAuth omezuje přístup na autorizovanou schránku.

5. RAG a Web Search
- RAG používá pouze schválené aktivní dokumenty.
- Web Search dostává pouze bezpečně sestavené veřejné dotazy.
- Externí obsah nesmí měnit oprávnění aplikace.

6. Odesílání odpovědí
- Gemini vytváří pouze návrh odpovědi.
- Reply Policy určuje příjemce a ověřuje e-mailové hlavičky.
- Gmail Sender provádí odeslání až po aplikační validaci.
- Model nemá přímé oprávnění k Gmail Send.

Autorizace nespoléhá pouze na vstupní API. Kontroly probíhají také při načítání dat, změnách databázového stavu a odesílání odpovědi.

### Jaké jsou bezpečnostní požadavky a kontrola (např. OWASP ASVS)?

- ID: security_requirements (povinné)
- Stav: **PŘEDPOKLAD**

SECURITY REQUIREMENTS – REPLY MCFLY

Bezpečnostní návrh vychází z principů least privilege, defense in depth, OWASP ASVS a bezpečného zpracování nedůvěryhodného AI obsahu.

1. Autentizace a autorizace
- Povinná IAM/OIDC autentizace Cloud Run endpointů.
- OAuth 2.0 pro Gmail API.
- Minimální oprávnění servisních účtů.
- Serverová kontrola mailbox_id, job_id a povolených operací.

2. Bezpečnost API
- HTTPS/TLS pro komunikaci.
- Validace vstupů pomocí Pydantic.
- Omezení velikosti požadavků a příloh.
- Strukturované chybové odpovědi bez citlivých údajů.
- Kontrolované timeouty, retry a rate limiting.

3. Bezpečnost příloh
- Povolené formáty PDF, MP3, WAV, JPEG a PNG.
- Kontrola MIME typu a skutečné signatury.
- Limity velikosti, počtu příloh, PDF stran a délky audia.
- Odmítnutí poškozených nebo neplatných souborů.
- Žádné vykonávání obsahu příloh.
- Antivirové skenování musí být doplněno před veřejným produkčním provozem.

4. AI bezpečnost
- Ochrana proti prompt injection.
- Oddělení systémových instrukcí od obsahu e-mailů, příloh, RAG a webových výsledků.
- Gemini nemůže přímo odesílat e-maily ani měnit oprávnění.
- Kontrola strukturovaného výstupu před odesláním.
- Nepředávání soukromých dat do veřejného Web Search.

5. Ochrana dat
- Minimalizace ukládaných informací.
- Secrets v Google Secret Manageru.
- Omezený přístup k PostgreSQL.
- Odstranění dočasných příloh po zpracování.
- Logování bez citlivého obsahu.
- Retenční a výmazová pravidla.

6. Spolehlivost a zneužití
- Deduplikace e-mailů pomocí PostgreSQL.
- Ochrana před e-mailovými smyčkami.
- Kontrolované retry.
- Bezpečné řešení DELIVERY_UNKNOWN.
- Monitoring chyb, neautorizovaných požadavků a neobvyklé zátěže.

7. Bezpečnostní testy
- Neplatný OIDC token.
- Neoprávněný přístup k endpointům.
- Prompt injection v e-mailu a přílohách.
- Poškozené nebo nadlimitní přílohy.
- Pokus o změnu příjemce odpovědi.
- Duplicitní a opakované události.
- Kontrola úniku citlivých dat do logů.

OWASP ASVS použijeme jako referenční checklist relevantních bezpečnostních kontrol. Formální certifikaci ani úplnou shodu s OWASP ASVS zatím netvrdíme.

### Kde budou secrets, jak rotují a kdo má přístup?

- ID: secrets_management (povinné)
- Stav: **PŘEDPOKLAD**

SECRETS MANAGEMENT – REPLY MCFLY

Použijeme Google Cloud Secret Manager jako centrální úložiště citlivé konfigurace.

1. Ukládané secrets
- Gmail OAuth refresh token.
- OAuth client secret, pokud je pro zvolený typ klienta vyžadován.
- Databázové přístupové údaje, pokud používáme heslovou autentizaci.
- Případné další API credentials.

2. Přístup
- Cloud Run Worker má oprávnění číst pouze potřebné secrets.
- Cloud Run Ingress nemá přístup k Gmail OAuth tokenům.
- Administrátor má přístup podle IAM a principu nejnižších oprávnění.
- Servisní účty používají Google IAM bez statických klíčů, pokud je to možné.

3. Rotace
- Secret Manager podporuje verzování secrets.
- Nová verze secretu se vytvoří před deaktivací původní.
- Po aktualizaci se ověří funkčnost integrace.
- Starou verzi lze deaktivovat až po úspěšném ověření.
- Gmail OAuth refresh token se obnoví nebo znovu autorizuje podle jeho platnosti a pravidel Google OAuth.
- Při podezření na kompromitaci se token revokuje a nahradí.

4. Lokální vývoj
- Secrets nejsou součástí Git repozitáře.
- Do repozitáře patří pouze .env.example bez skutečných hodnot.
- Lokální přihlašovací údaje se spravují odděleně.
- Produkční secrets se nepoužívají v automatizovaných unit testech.

5. Monitoring a audit
- Sledujeme chyby přístupu k Secret Manageru.
- Přístupy a změny oprávnění lze auditovat pomocí Cloud Audit Logs.
- OAuth chyby vyvolají provozní upozornění.
- Secrets se nikdy nezapisují do aplikačních logů.

6. Odpovědnost
- Vlastník konfigurace: AI Engineer / Cloud Engineer.
- Spravovaná infrastruktura: Google Cloud.
- Přístupová práva: IAM podle servisních rolí.

Konkrétní harmonogram rotace a postup obnovy OAuth autorizace bude ověřen během implementace.

### Jak chráníš data přenosem a v klidu a spravuješ klíče?

- ID: encryption (povinné)
- Stav: **PŘEDPOKLAD**

ENCRYPTION AND KEY MANAGEMENT – REPLY MCFLY

1. Data při přenosu (in transit)
- Komunikace s Gmail API, Vertex AI Gemini a Google Cloud API používá HTTPS/TLS.
- Pub/Sub push a Cloud Tasks komunikují s Cloud Run přes HTTPS.
- Připojení k PostgreSQL používá zabezpečený způsob připojení podporovaný Cloud SQL.
- Nešifrovaný veřejný přenos citlivých dat není povolen.

2. Data v klidu (at rest)
- Cloud SQL používá šifrování uložených dat spravované Google Cloud.
- Secret Manager chrání uložené OAuth tokeny a secrets.
- Gmail zajišťuje ochranu zpráv a příloh podle vlastních bezpečnostních mechanismů.
- Dočasné soubory jsou omezeny na dobu zpracování a následně odstraněny.

3. Správa šifrovacích klíčů
- Pro PoC preferujeme Google-managed encryption keys.
- Nevytváříme vlastní systém správy kryptografických klíčů.
- Pokud vznikne požadavek na zákaznicky spravované klíče, lze vyhodnotit Cloud KMS a CMEK podle podpory konkrétní služby.

4. Ochrana přístupových údajů
- OAuth tokeny a secrets jsou v Secret Manageru.
- Servisní identity využívají IAM.
- Přístup ke klíčům a tajným údajům je omezen na potřebné komponenty.

5. Ochrana soukromých dat
- E-maily a přílohy se neukládají trvale bez potřeby.
- PostgreSQL obsahuje pouze nezbytný stav a metadata.
- Provozní logy neobsahují soukromý obsah ani autentizační údaje.
- Web Search nedostává soukromé e-mailové informace.

6. Ověření
- Kontrola HTTPS/TLS integrací.
- Kontrola připojení Cloud SQL.
- Kontrola IAM přístupu k Secret Manageru.
- Ověření šifrování a konfigurace záloh.
- Kontrola dočasných souborů a citlivých logů.

CÍL:
Zajistit ochranu dat při přenosu i uložení bez provozování vlastní kryptografické infrastruktury.

Konkrétní konfigurace šifrování a její úspěšné ověření budou doloženy během deploymentu.

### Jaké jsou 3 největší hrozby a obrany?

- ID: threat_model (povinné)
- Stav: **PŘEDPOKLAD**

TOP 3 SECURITY THREATS – REPLY MCFLY

1. Prompt Injection a neoprávněné AI akce

Hrozba:
Útočník vloží škodlivé instrukce do e-mailu, PDF, obrázku, audio přílohy nebo webového výsledku. Pokusí se změnit příjemce, obejít pravidla nebo získat citlivá data.

Obrana:
- Veškerý externí obsah je považován za nedůvěryhodný.
- Systémové instrukce jsou oddělené od uživatelského obsahu.
- Gemini nemá přímá oprávnění k Gmail Send ani administraci databáze.
- Příjemce a Gmail threadId určuje backend.
- Výstup prochází strukturální a bezpečnostní validací.
- Web Search nedostává soukromý obsah e-mailů.

Test:
Simulovat prompt injection v e-mailu, PDF a webovém výsledku a ověřit, že nevyvolá nepovolenou operaci.

2. Únik citlivých dat a kompromitace přístupů

Hrozba:
Neoprávněný přístup k Gmail schránce, OAuth tokenům, přílohám nebo databázi může způsobit únik soukromých informací.

Obrana:
- Google Cloud IAM a princip nejnižších oprávnění.
- OAuth 2.0 s minimálními Gmail scopes.
- Secret Manager pro přístupové údaje.
- Povinná OIDC autentizace Cloud Run endpointů.
- Zabezpečené databázové připojení.
- TLS komunikace.
- Minimalizace dat a zákaz logování e-mailového obsahu.
- Syntetická data během PoC.

Test:
Neautorizované API požadavky, kontrola IAM rolí, pokus o přístup k secrets a kontrola citlivého obsahu logů.

3. Duplicitní nebo neoprávněné odeslání e-mailu

Hrozba:
Opakované Pub/Sub/Cloud Tasks události, restart Workeru, race conditions nebo nejasný výsledek Gmail Send mohou způsobit duplicitní nebo nesprávně adresovanou odpověď.

Obrana:
- UNIQUE(mailbox_id, gmail_message_id).
- Atomická rezervace email job.
- Lease s expirací.
- Outbox s UNIQUE(job_id).
- Stabilní outbound_message_id.
- Kontrola příjemce a Gmail threading hlaviček.
- Stav DELIVERY_UNKNOWN při nejasném odeslání.
- Ověření Gmailu před případným opakováním.
- Ignorování vlastních a automatických odpovědí.

Test:
Opakované doručení stejné události, souběžné spuštění Workerů, restart během odesílání a simulace timeoutu Gmail API.

PRINCIP:
Nejdůležitějšími bezpečnostními cíli jsou ochrana soukromých dat, zabránění neoprávněným AI akcím a bezpečné odeslání maximálně jedné automatické odpovědi na příchozí zprávu.

### Pokud zpracováváš osobní data: účel, právní základ, role správce/zpracovatele?

- ID: privacy_basis (povinné)
- Stav: **PŘEDPOKLAD**

OCHRANA OSOBNÍCH ÚDAJŮ – REPLY MCFLY

1. Zpracovávané osobní údaje
- E-mailové adresy odesílatelů a příjemců.
- Obsah příchozích a odchozích e-mailů.
- Historie komunikace v aktuálním Gmail vlákně.
- Přílohy PDF, MP3, WAV, JPEG a PNG.
- Technická metadata zpráv a jejich zpracování.

2. Účel zpracování
- Automatické přijetí a vyhodnocení e-mailového dotazu.
- Analýza obsahu zprávy a příloh.
- Zohlednění předchozí komunikace (Conversation History).
- Vyhledání relevantních informací prostřednictvím RAG.
- Generování a odeslání odpovědi do původního vlákna.
- Zajištění bezpečnosti, prevence duplicit a diagnostiky chyb.

3. Právní základ podle GDPR
- Pro PoC používáme syntetická testovací data bez skutečných osobních údajů, pokud je to možné.
- Pro případ zpracování reálných osobních údajů je nutné určit právní základ podle článku 6 GDPR.
- Podle konkrétního použití může přicházet v úvahu plnění smlouvy nebo oprávněný zájem.
- Právní základ musí schválit správce osobních údajů před produkčním provozem.

4. Role a odpovědnosti
- Správce osobních údajů: subjekt, který určuje účel a prostředky zpracování.
- Google: poskytovatel Gmail a Google Cloud služeb; konkrétní role se řídí příslušnými smluvními podmínkami.
- AI Engineer: implementace technických a organizačních bezpečnostních opatření.
- Přesné rozdělení rolí správce a zpracovatele musí být právně ověřeno.

5. Ochranná opatření
- Minimalizace zpracovávaných údajů.
- OAuth 2.0 a princip nejnižších oprávnění.
- IAM/OIDC autentizace cloudových služeb.
- Secret Manager pro přístupové údaje.
- Šifrovaná komunikace a zabezpečená databáze.
- Oddělení historie vláken od RAG znalostní báze.
- Zákaz předávání soukromých dat do veřejného Web Search.
- Odstranění dočasných příloh po zpracování.
- Omezená retence metadat a logů.

6. Před produkčním použitím
- Potvrdit právní základ a role účastníků.
- Ověřit podmínky zpracování dat u poskytovatelů.
- Stanovit retenční pravidla.
- Posoudit případné přeshraniční přenosy.
- Posoudit potřebu DPIA podle charakteru a rizik zpracování.

Architektura zahrnuje technické prostředky ochrany dat, ale nepředstavuje dokončené právní posouzení GDPR.

### Jak odděluješ data mezi účty a tenanty?

- ID: tenant_authorization (doplňkové)
- Stav: **PŘEDPOKLAD**

IZOLACE DAT A TENANTŮ – REPLY MCFLY

1. Multitenancy
- PoC nepoužívá multitenant architekturu.
- Aplikace pracuje s jednou dedikovanou Gmail schránkou.
- Neexistují samostatné zákaznické účty ani organizace sdílející aplikaci.
- Tenant-based RBAC ani tenant-specific databázová schémata nejsou potřebná.

2. Izolace e-mailových vláken
- Každá zpráva je identifikována pomocí mailbox_id a gmail_message_id.
- Každé vlákno je identifikováno pomocí gmail_thread_id.
- Conversation History načítá pouze zprávy z aktuálního Gmail vlákna.
- Informace z nesouvisejících vláken nesmějí vstoupit do AI kontextu.

3. Databázová izolace
- PostgreSQL eviduje zprávy pomocí unikátní kombinace mailbox_id a gmail_message_id.
- Worker ověřuje příslušnost úlohy k autorizované schránce.
- Přístup do databáze je omezen na autorizované servisní identity.
- RAG dokumenty jsou oddělené od historie e-mailových konverzací.

4. Autorizace
- Gmail OAuth umožňuje přístup pouze k autorizované schránce.
- Cloud Run endpointy vyžadují IAM/OIDC.
- Backend serverově kontroluje mailbox_id, job_id a gmail_thread_id.
- Příjemce odpovědi a cílové vlákno určuje backend, nikoliv Gemini.

5. Budoucí rozšíření na více tenantů
- Vyžadovalo by samostatnou tenant identitu a autorizaci.
- Databázové dotazy by musely důsledně filtrovat tenant_id.
- Bylo by nutné oddělit OAuth credentials a RAG znalostní báze.
- Izolace by se ověřovala bezpečnostními a integračními testy.

Pro současné PoC je klíčová izolace Gmail vláken, nikoliv izolace mezi více organizacemi.

### Jak validuješ nebezpečné vstupy, upload, limity a výstupní encoding?

- ID: input_validation (doplňkové)
- Stav: **PŘEDPOKLAD**

INPUT VALIDATION – REPLY MCFLY

1. HTTP API
- FastAPI + Pydantic validují strukturu požadavků.
- Kontrolují povinná pole, datové typy a povolené hodnoty.
- Ověřují mailbox_id, job_id a formát Pub/Sub notifikací.
- Neplatné nebo neoprávněné požadavky se odmítají.

2. E-mailový obsah
- MIME struktura se parsuje bezpečně.
- Kontrolují se podporované formáty a velikosti.
- HTML obsah e-mailů se nepovažuje za důvěryhodný.
- E-mailové hlavičky nejsou zdrojem oprávnění aplikace.
- Vlastní a známé automatické odpovědi se filtrují.

3. Povolené přílohy
- PDF, MP3, WAV, JPEG a PNG.
- Maximálně 5 příloh na zprávu.
- Maximálně 20 MiB celkem.
- PDF: maximálně 5 MiB na soubor a 30 stran celkem.
- Audio: maximálně 10 MiB a 180 sekund.
- JPEG/PNG: maximálně 5 MiB a 10 MP.

4. Validace souborů
- Kontrola MIME typu a skutečné signatury.
- Ověření skutečné velikosti a struktury.
- Odmítnutí poškozených nebo šifrovaných nečitelných PDF.
- Kontrola délky audia pomocí ffprobe.
- Kontrola rozměrů obrázků a ochrana proti decompression bombs.
- Timeouty parserů.
- Žádné vykonávání obsahu souborů.

5. Prompt injection
- E-maily, přílohy, RAG dokumenty a webové výsledky jsou nedůvěryhodné vstupy.
- Jejich instrukce nesmějí měnit oprávnění, příjemce ani systémová pravidla.
- Gemini nemá přímý přístup k Gmail Send.
- Výstup modelu prochází strukturální validací.

6. Output encoding
- Odpověď se vytváří jako správně kódovaná MIME zpráva.
- Hlavičky se sestavují pomocí bezpečné e-mailové knihovny.
- Dynamické hodnoty se nesmějí nekontrolovaně vkládat do e-mailových hlaviček.
- HTML výstup se musí bezpečně escapovat nebo sanitizovat.
- Pro první verzi preferujeme jednoduchou text/plain odpověď.

7. Neplatné vstupy
- Nepodporované přílohy se odmítají.
- Důvod odmítnutí se eviduje bez logování citlivého obsahu.
- Použije se definovaná bezpečná odpověď nebo NEEDS_REVIEW.

Antivirové skenování musí být doplněno a otestováno před veřejným produkčním provozem.

### Jak řešíš cookies, session expiraci, CSRF, token storage?

- ID: session_policy (doplňkové)
- Stav: **PŘEDPOKLAD**

SESSION POLICY – REPLY MCFLY

Aplikace nemá vlastní webové uživatelské rozhraní ani uživatelské přihlašovací sessions.

1. Cookies a sessions
- Aplikace nepoužívá uživatelské session cookies.
- Koncoví uživatelé komunikují prostřednictvím Gmailu.
- Správcovské přihlášení zajišťuje Google Cloud Console a Google IAM.
- Aplikace neimplementuje vlastní session management.

2. CSRF
- Produkční endpointy nejsou určeny pro webové formuláře ani browser-based sessions.
- Autentizace probíhá pomocí OIDC Bearer tokenů servisních identit.
- Klasická cookie-based CSRF ochrana není pro současné API relevantní.
- Pokud vznikne webové UI, bude nutné navrhnout odpovídající CSRF ochranu.

3. Gmail OAuth 2.0
- Správce provede jednorázový OAuth authorization flow.
- OAuth refresh token je uložen v Google Secret Manageru.
- Access token se obnovuje podle expirace.
- Tokeny se neukládají do zdrojového kódu, logů ani klientských cookies.

4. Service-to-service tokeny
- Pub/Sub a Cloud Tasks používají OIDC servisní identity.
- Cloud Run ověřuje identitu volající služby.
- Krátkodobé tokeny se získávají prostřednictvím Google identity mechanismů.
- Servisní účty nepoužívají vlastní uživatelské sessions.

5. Token storage a rotace
- Dlouhodobé OAuth credentials se uchovávají v Secret Manageru.
- Přístup je omezený pomocí IAM.
- Při expiraci nebo revokaci Gmail refresh tokenu je nutná opětovná autorizace.
- Chyby OAuth jsou monitorovány.

6. Bezpečnost
- HTTPS/TLS pro API komunikaci.
- Minimální OAuth scopes.
- Žádné statické servisní klíče ve zdrojovém kódu.
- Nepovolený přístup k endpointům se odmítá.

Zvolený přístup eliminuje potřebu vlastních uživatelských sessions a jejich správy.

### Jaké bezpečnostní události loguješ bez citlivého payloadu?

- ID: audit_security (doplňkové)
- Stav: **PŘEDPOKLAD**

SECURITY AUDIT LOGGING – REPLY MCFLY

Použijeme Cloud Logging a Cloud Monitoring pro strukturované provozní a bezpečnostní události.

1. Autentizace a autorizace
- Neúspěšné OIDC ověření.
- Neautorizované HTTP požadavky (401/403).
- Zamítnutý přístup k Gmail schránce.
- Chyby Gmail OAuth.
- Neoprávněné pokusy o přístup k Secret Manageru.

2. Zpracování e-mailů
- email_received
- email_queued
- email_processing_started
- email_reply_sent
- email_processing_failed
- duplicate_skipped

3. Bezpečnost příloh
- attachment_rejected
- Nepodporovaný formát.
- Překročená velikost nebo délka.
- Poškozený nebo nečitelný soubor.
- Chyba bezpečnostní validace.

4. AI bezpečnost
- Zamítnutý AI výstup.
- Neplatná struktura odpovědi.
- Pokus o změnu nepovoleného příjemce.
- Detekovaný nebo testovaný prompt injection scénář.
- Neúspěšné RAG/Web Search ověření.

5. Spolehlivost a outbox
- Změny stavu email job.
- Retry a vyčerpání pokusů.
- DELIVERY_UNKNOWN.
- Recovery přerušené úlohy.
- Zamítnutý duplicitní send.

6. Provozní a administrativní události
- Deployment nové Cloud Run revize.
- Databázová migrace.
- Změna IAM oprávnění.
- Aktualizace secrets.
- Obnova Gmail Watch.
- Výpadky externích API.

7. Struktura logu
- timestamp
- event_type
- correlation_id / job_id
- component
- operation
- status
- error_code
- duration_ms
- retry_count

8. Ochrana citlivých dat
- Nelogovat těla e-mailů.
- Nelogovat obsah ani názvy citlivých příloh.
- Nelogovat OAuth tokeny a secrets.
- Nelogovat celé AI prompty a odpovědi.
- Identifikátory a adresy minimalizovat nebo pseudonymizovat.
- Nastavit přístupová a retenční pravidla logů.

9. Monitoring
- Výstrahy při opakovaných autentizačních chybách.
- Výstrahy při zvýšené chybovosti API.
- Výstrahy při neobvyklém počtu duplicit.
- Sledování překročení 120sekundového limitu.

CÍL:
Zajistit dohledatelnost zpracování a bezpečnostních incidentů bez ukládání soukromého obsahu komunikace do provozních logů.

### Jak budeš skenovat závislosti, kontejnery a tajemství v CI?

- ID: dependency_security (doplňkové)
- Stav: **PŘEDPOKLAD**

DEPENDENCY AND SUPPLY CHAIN SECURITY – REPLY MCFLY

Použijeme automatizované bezpečnostní kontroly v CI pipeline a před nasazením Docker image do Cloud Run.

1. Python dependencies
- Používat verzované a uzamčené závislosti.
- Automatické skenování známých zranitelností pomocí pip-audit.
- Kontrola závislostí při každém Pull Requestu.
- Kritické zranitelnosti musí být odstraněny nebo zdokumentovaně vyhodnoceny před deploymentem.

2. Docker image
- Používat oficiální a udržované base images.
- Minimalizovat počet instalovaných balíčků.
- Spouštět aplikaci jako neprivilegovaný uživatel.
- Skenovat image pomocí Trivy nebo Google Artifact Analysis.
- Nevkládat credentials do Docker image.

3. Secrets scanning
- Automatická kontrola Git repozitáře pomocí Gitleaks.
- Detekce API klíčů, OAuth tokenů a databázových hesel.
- Secrets uchovávat mimo Git v Google Secret Manageru.
- Při úniku okamžitě revokovat a nahradit kompromitované credentials.

4. Static Application Security Testing
- Ruff pro kontrolu Python kódu.
- Bandit pro základní Python security analýzu.
- Kontrola nebezpečného parsování, shell příkazů a práce se soubory.
- Bezpečnostní testy FastAPI endpointů.

5. CI pipeline
- Checkout zdrojového kódu.
- Instalace uzamčených závislostí.
- Lint a statická analýza.
- pip-audit.
- Gitleaks.
- pytest unit/integration tests.
- Docker build.
- Trivy/Artifact Analysis scan.
- Deployment pouze při splnění definovaných kontrol.

6. Deployment security
- Cloud Run používá autorizovanou servisní identitu.
- Build a deploy identity mají oddělená minimální oprávnění.
- Produkční secrets se nepředávají build procesu.
- Nasazovaný image je identifikovaný konkrétním digestem.

7. Pravidla pro zranitelnosti
- Kritické a vysoké nálezy blokují deployment, pokud nejsou výslovně schválenou výjimkou.
- Výjimky musí mít zdůvodnění a termín nápravy.
- Pravidelně aktualizovat závislosti a base image.
- Po aktualizaci spustit regresní testy.

CÍL:
Minimalizovat riziko zranitelných knihoven, kompromitovaných kontejnerů a úniku tajných údajů.

Konkrétní CI platforma, skenery a bezpečnostní pravidla budou finálně vybrány a ověřeny během implementace.

### Kdo přijímá a triaguje reporty zranitelností a incidenty?

- ID: security_contacts (doplňkové)
- Stav: **PŘEDPOKLAD**

SECURITY CONTACTS – REPLY MCFLY

1. Odpovědná osoba
- Primární kontakt: AI Engineer / Solution Architect.
- V rámci PoC zastává také roli Security Owner.
- Odpovídá za přijetí, klasifikaci, řešení a evidenci bezpečnostních nálezů.

2. Zdroje bezpečnostních hlášení
- Google Cloud Monitoring a Cloud Logging.
- Cloud Audit Logs a IAM události.
- Výsledky bezpečnostních kontrol v CI.
- Automatické kontroly závislostí a Docker image.
- Ručně nahlášené zranitelnosti nebo podezřelé chování.

3. Triage
- CRITICAL: Únik přístupových údajů, neoprávněné odesílání e-mailů nebo potvrzený únik citlivých dat.
- HIGH: Zranitelnost umožňující neoprávněný přístup nebo obejití bezpečnostních pravidel.
- MEDIUM: Omezená bezpečnostní slabina bez potvrzeného zneužití.
- LOW: Nízkorizikový nález nebo doporučení ke zlepšení.

4. Postup
- Přijmout a zaevidovat hlášení.
- Posoudit závažnost a dopad.
- Určit dotčené komponenty.
- Provést potřebná ochranná opatření.
- Opravit zranitelnost a ověřit opravu testem.
- Uzavřít nález s technickým důkazem.

5. Eskalace
- Bezpečnostní incident týkající se osobních údajů se předává odpovědnému správci údajů.
- Incident poskytovatele Google Cloud se řeší prostřednictvím dostupných support kanálů.
- Při kritickém incidentu lze dočasně pozastavit zpracování a odesílání e-mailů.

6. Evidence
- Každý nález má identifikátor, závažnost, odpovědnou osobu, stav a záznam o nápravě.
- Citlivé údaje ani přístupové tokeny se neukládají do incidentních logů.

Konkrétní kontaktní adresa a eskalační SLA nejsou v současném PoC stanoveny.

### Jak vyřídíš přístup, opravu, export a smazání osobních dat?

- ID: data_subject_rights (doplňkové)
- Stav: **PŘEDPOKLAD**

PRÁVA SUBJEKTŮ ÚDAJŮ – REPLY MCFLY

1. Přijetí žádosti
- Žádost přijímá správce osobních údajů.
- Před zpřístupněním nebo změnou údajů je nutné ověřit identitu a oprávnění žadatele.
- AI asistent neprovádí automatický výmaz ani export pouze na základě e-mailového požadavku.

2. Identifikace dat
- Gmail: e-maily, přílohy a historie komunikace.
- PostgreSQL: email_jobs, email_outbox a metadata zpracování.
- Cloud Logging: omezené provozní a bezpečnostní záznamy.
- Secret Manager: technické přístupové údaje, nikoliv uživatelská evidence.

3. Právo na přístup
- Vyhledat relevantní údaje v Gmailu a PostgreSQL.
- Posoudit případná práva dalších osob.
- Připravit přehled zpracovávaných osobních údajů.
- Předat informace bezpečným způsobem.

4. Právo na opravu
- Ověřit požadovanou změnu.
- Opravit údaje, které aplikace skutečně spravuje.
- Změny původního e-mailového obsahu řešit v mezích možností Gmailu a právních pravidel.
- Zachovat integritu provozních a auditních záznamů.

5. Právo na export
- Exportovat relevantní údaje v běžně používaném strojově čitelném formátu, pokud je právo na přenositelnost použitelné.
- Použít standardní možnosti Gmailu a PostgreSQL.
- Exportovat pouze oprávněný rozsah údajů.

6. Právo na výmaz
- Posoudit, zda jsou splněny podmínky výmazu a neexistuje důvod k dalšímu uchování.
- Odstranit příslušná data z aktivních úložišť.
- Respektovat databázové vazby a retenční pravidla.
- Zajistit expiraci kopií v zálohách.
- Po obnově starší zálohy znovu aplikovat relevantní požadavky na výmaz.

7. Evidence a lhůty
- Evidovat přijetí žádosti, ověření identity, provedené kroky a výsledek.
- Standardní GDPR lhůta pro odpověď je jeden měsíc, s možností zákonného prodloužení v příslušných případech.
- Žádosti vyřizuje odpovědný správce údajů, nikoliv autonomní AI model.

Pro PoC používáme syntetická testovací data. Proces musí být formálně dopracován před použitím reálných osobních údajů.

### Jaký je proces vyhodnocení a hlášení bezpečnostního incidentu?

- ID: incident_disclosure (doplňkové)
- Stav: **PŘEDPOKLAD**

INCIDENT RESPONSE AND DISCLOSURE – REPLY MCFLY

1. Detekce
- Cloud Monitoring, Cloud Logging a Cloud Audit Logs.
- Chyby Gmail OAuth a neautorizované API požadavky.
- Podezřelé odesílání e-mailů nebo zvýšený počet duplicit.
- Zjištěný únik secrets nebo osobních údajů.
- Bezpečnostní nálezy z CI a ruční hlášení.

2. Prvotní vyhodnocení
- Zaevidovat incident a čas jeho zjištění.
- Identifikovat dotčené služby, data a přístupové identity.
- Určit závažnost, rozsah a možný dopad.
- Rozlišit provozní chybu od bezpečnostního incidentu.
- Posoudit, zda došlo k porušení zabezpečení osobních údajů.

3. Omezení dopadu
- Při podezření na kompromitaci deaktivovat nebo revokovat příslušné credentials.
- Omezit oprávnění kompromitované identity.
- Podle potřeby pozastavit Cloud Tasks zpracování nebo Gmail odesílání.
- Zachovat nezbytné technické důkazy bez zbytečného kopírování citlivých dat.

4. Náprava
- Opravit zranitelnou konfiguraci nebo aplikaci.
- Aktualizovat závislosti nebo Docker image.
- Obnovit bezpečné přístupové údaje.
- Zkontrolovat integritu email_jobs, email_outbox a synchronizačních checkpointů.
- Ověřit, zda nedošlo k neoprávněnému odeslání odpovědí.

5. Oznámení incidentu
- Bezpečnostní incident se eskaluje odpovědnému Security Ownerovi.
- Incident s osobními údaji se předává správci osobních údajů.
- Pokud vznikne povinnost podle GDPR čl. 33, správce oznámí porušení zabezpečení dozorovému úřadu bez zbytečného odkladu, pokud možno do 72 hodin od okamžiku, kdy se o něm dozvěděl.
- Pokud jsou splněny podmínky GDPR čl. 34, správce informuje také dotčené subjekty údajů.
- Případné smluvní oznamovací povinnosti se řeší podle příslušných podmínek.

6. Recovery
- Obnovit služby až po ověření odstranění příčiny.
- Otestovat Gmail synchronizaci a bezpečné odesílání.
- Zkontrolovat, že nedojde k duplicitnímu odeslání.
- Zaznamenat dobu výpadku a dopad na SLA/latenci.

7. Post-incident review
- Zdokumentovat příčinu, dopad, časovou osu a nápravná opatření.
- Doplnit regresní nebo bezpečnostní test.
- Aktualizovat monitoring a provozní dokumentaci.

Tento postup je návrhem pro PoC. Formální incident response plán a eskalační kontakty ještě nejsou schváleny.

### Kde je výsledek bezpečnostní kontroly a evidence oprav?

- ID: security_review_evidence (doplňkové)
- Stav: **PŘEDPOKLAD**

SECURITY REVIEW EVIDENCE – REPLY MCFLY

Aktuální stav:
- Bezpečnostní požadavky jsou definovány v architektonickém návrhu.
- Formální security review a penetrační test zatím nebyly provedeny.
- Výsledky skenování, bezpečnostních testů a oprav zatím nejsou dostupné.

Plánované umístění dokumentace v repozitáři:

docs/security/
- threat-model.md – identifikované hrozby a obrany.
- security-review.md – výsledky bezpečnostní kontroly.
- findings.md – evidence zranitelností a nápravných opatření.
- incident-response.md – postup řešení incidentů.
- security-test-results.md – výsledky bezpečnostních testů.

1. Obsah security review
- Kontrola IAM a principu nejnižších oprávnění.
- Ověření OIDC autentizace Cloud Run.
- Kontrola Gmail OAuth scopes.
- Kontrola přístupu k Secret Manageru.
- Ověření zabezpečení PostgreSQL.
- Validace příloh a ochrana proti prompt injection.
- Kontrola bezpečného Gmail odesílání a idempotence.
- Kontrola logování citlivých dat.

2. Automatizované důkazy
- Výsledky pytest security tests.
- Výsledky pip-audit.
- Výsledky skenování Docker image.
- Výsledky secrets scanning.
- CI build a test reporty.
- Relevantní Cloud Audit Logs.

3. Evidence nálezů
Každý bezpečnostní nález bude obsahovat:
- Identifikátor nálezu.
- Popis a závažnost.
- Dotčenou komponentu.
- Odpovědnou osobu.
- Nápravné opatření.
- Stav řešení.
- Odkaz na commit nebo Pull Request.
- Výsledek ověřovacího testu.
- Datum uzavření.

4. Podmínky dokončení
- Kritické bezpečnostní nálezy musí být vyřešeny před veřejným provozem.
- Bezpečnostní testy musí úspěšně projít.
- Přístupová oprávnění musí být ověřena.
- Opravy musí být doloženy regresními testy.
- Výsledky musí být součástí projektové dokumentace.

Security review bude provedeno po implementaci základní cloudové infrastruktury a před finálním end-to-end demonstračním testem.

Bezpečnostní dokumenty uvedené výše jsou plánované výstupy, nikoliv již existující a schválené důkazy.

## 09 · Frontend, přístupnost a UX implementace

*Cíl:* Proměň flows a stavy do obrazovek a konkrétních komponent.

*Gate:* Obrazovky, stav UI, formuláře, odpovědnost a testy jsou navržené.

### Jakou frontend platformu/framework/versi použiješ a proč?

- ID: frontend_framework (povinné)
- Stav: **PŘEDPOKLAD**

FRONTEND TECHNOLOGIE – REPLY MCFLY

Samostatný webový frontend není součástí aplikace.

1. Uživatelské rozhraní:
- E-mail prostřednictvím Gmailu nebo libovolného e-mailového klienta.
- Uživatel odešle zprávu na dedikovanou Gmail adresu.
- Automatickou odpověď obdrží ve stejném e-mailovém vlákně.
- Není potřeba instalace aplikace, registrace ani přihlášení.

2. Administrace:
- Google Cloud Console pro správu infrastruktury.
- Cloud Logging a Monitoring pro diagnostiku.
- Gmail pro kontrolu přijatých a odeslaných zpráv.

3. Frontend framework:
- React, Next.js, Angular ani Vue nejsou vyžadovány.
- Nevytváříme vlastní SPA ani server-rendered web.
- Backend používá Python/FastAPI, ale neposkytuje uživatelské UI.

4. Důvody:
- Požadované rozhraní je e-mail.
- Nižší implementační a provozní složitost.
- Menší bezpečnostní plocha.
- Žádná správa webových sessions, cookies ani uživatelských hesel.
- Vývoj se soustředí na AI zpracování a splnění 120sekundového limitu.

Případné administrativní webové UI lze doplnit později jako samostatnou aplikaci, pokud vznikne konkrétní požadavek.

### Jaké stránky, navigace a chráněné routy existují?

- ID: frontend_routes (povinné)
- Stav: **PŘEDPOKLAD**

FRONTEND ROUTES – REPLY MCFLY

Aplikace nemá vlastní webové stránky, navigaci ani frontend routy.

1. Uživatelský přístup:
- Uživatel komunikuje s dedikovanou Gmail schránkou.
- Nový e-mail zahajuje zpracování.
- Navazující zpráva ve stejném vlákně využívá Conversation History.
- Odpověď se doručuje do původního Gmail vlákna.

2. Administrátorský přístup:
- Google Cloud Console – infrastruktura a konfigurace.
- Cloud Logging / Monitoring – provozní diagnostika.
- Gmail – kontrola e-mailové komunikace.
- Přístup zabezpečuje Google IAM nebo autentizace Gmail účtu.

3. Interní backend endpointy:
- POST /events/gmail – příjem Pub/Sub notifikací.
- POST /tasks/sync – synchronizace Gmail schránky.
- POST /tasks/process – zpracování konkrétního e-mailu.
- POST /tasks/maintenance – údržba a recovery.

Tyto endpointy nejsou frontend routy. Jsou určeny výhradně autorizovaným cloudovým službám.

4. Bezpečnost:
- Žádné veřejné administrační stránky.
- Žádné anonymně přístupné aplikační endpointy.
- Povinná IAM/OIDC autentizace interních API.

V první verzi není potřeba frontend router ani vlastní systém chráněných webových stránek.

### Jaké chování patří do UI a co je vždy ověřováno backendem?

- ID: frontend_responsibilities (povinné)
- Stav: **PŘEDPOKLAD**

ODPOVĚDNOSTI UI A BACKENDU – REPLY MCFLY

1. Uživatelské rozhraní – e-mailový klient:
- Vytvoření a odeslání e-mailového dotazu.
- Připojení PDF, MP3, WAV, JPEG nebo PNG přílohy.
- Zobrazení přijaté odpovědi.
- Pokračování komunikace ve stejném vlákně.

2. Backend – Cloud Run Worker:
- Ověření nové nepřečtené zprávy.
- Validace MIME obsahu a příloh.
- Kontrola podporovaných formátů a velikostních limitů.
- Identifikace gmail_message_id a gmail_thread_id.
- Deduplikace a evidence stavu v PostgreSQL.
- Načtení Conversation History pouze z aktuálního vlákna.
- Výběr relevantních RAG a Web Search zdrojů.
- Volání Vertex AI Gemini.
- Validace struktury a bezpečnosti AI odpovědi.
- Určení oprávněného příjemce.
- Zachování Gmail threading hlaviček.
- Kontrolované odeslání odpovědi.

3. Bezpečnostní pravidla:
- E-mailový klient není důvěryhodná bezpečnostní hranice.
- Veškerý příchozí obsah je nedůvěryhodný.
- Backend nespoléhá na údaje o oprávněních dodané v e-mailu.
- Gemini nemůže měnit příjemce, oprávnění ani samostatně odesílat zprávy.

PRINCIP:
Uživatelský e-mailový klient slouží pouze pro komunikaci. Veškerá aplikační logika, validace, autorizace a odesílání jsou odpovědností backendu.

### Jak UI zobrazí loading, empty, success, error, retry a offline stav?

- ID: frontend_states (povinné)
- Stav: **PŘEDPOKLAD**

UI STATES – REPLY MCFLY

Aplikace nemá vlastní interaktivní frontend. Stavy zpracování se proto nezobrazují pomocí webových komponent.

1. Loading / Processing
- Uživatel po odeslání e-mailu čeká na odpověď.
- Backend eviduje stav QUEUED nebo PROCESSING.
- Stav je dostupný správci prostřednictvím PostgreSQL a provozních logů.
- Není implementován uživatelský progress indicator.

2. Empty
- Pokud nejsou nové nepřečtené zprávy, systém nevytváří žádné zpracovatelské úlohy.
- Worker zůstává připraven na další událost.
- Cloud Run může škálovat na nulu.

3. Success
- Backend odešle odpověď do původního Gmail vlákna.
- Uživatel ji vidí ve svém e-mailovém klientovi.
- PostgreSQL eviduje stav SENT.

4. Error
- Dočasná chyba: RETRY_PENDING.
- Trvalá chyba: FAILED.
- Nutná ruční kontrola: NEEDS_REVIEW.
- Nejasné odeslání: DELIVERY_UNKNOWN.
- Chybové stavy jsou dostupné správci přes logy a monitoring.

5. Retry
- Cloud Tasks automaticky opakuje vhodné dočasně neúspěšné úlohy.
- PostgreSQL chrání před duplicitním zpracováním.
- Uživateli se neposílá samostatné oznámení o každém retry.

6. Offline / Service unavailable
- Pokud je některá služba nedostupná, systém použije retry nebo recovery podle charakteru chyby.
- Při neobnovitelném selhání se incident zaznamená.
- Správce jej řeší prostřednictvím Cloud Monitoring.
- Nelze garantovat odpověď do 120 sekund během výpadku infrastruktury.

7. Uživatelská komunikace při chybě
- Pro bezpečně identifikované neplatné přílohy může aplikace odeslat definovanou chybovou odpověď.
- Při nejasném výsledku odeslání nesmí automaticky vytvářet další zprávu.
- Samostatné uživatelské stavové rozhraní není pro PoC požadováno.

CÍL:
Zachovat jednoduché e-mailové UX a řídit technické stavy zpracování na backendu.

### Jak vypadá design system a znovupoužitelné komponenty?

- ID: ui_components (doplňkové)
- Stav: **PŘEDPOKLAD**

DESIGN SYSTEM – REPLY MCFLY

Pro počáteční PoC nevytváříme vlastní webový design system ani knihovnu UI komponent.

1. Uživatelské rozhraní
- Gmail nebo jiný e-mailový klient uživatele.
- Vzhled a ovládání zajišťuje použitý e-mailový klient.
- Reply McFly nevykresluje vlastní webové komponenty.

2. Výstupní e-mail
- Standardní textová odpověď (text/plain).
- Přehledná struktura, krátké odstavce a srozumitelný jazyk.
- Zachování původního e-mailového vlákna.
- Podle potřeby uvedení relevantních zdrojových odkazů.
- Bez vlastních interaktivních HTML prvků.

3. Znovupoužitelné aplikační komponenty
- EmailOrchestrator / WorkflowRunner.
- Attachment Validator.
- Conversation History Provider.
- RAG Provider.
- Web Search Provider.
- Gemini Adapter.
- Reply Policy + Gmail Sender.

Jde o backendové moduly, nikoliv UI komponenty.

4. Administrace
- Používá Google Cloud Console, Cloud Logging a Gmail.
- Nevytváříme vlastní dashboard ani administrační frontend.

5. Budoucí rozšíření
- Pokud vznikne požadavek na administrační UI, zvolíme frontend framework a design system samostatným architektonickým rozhodnutím.
- Pro současné PoC by vlastní design system znamenal zbytečnou komplexitu.

DŮVOD:
Hlavním uživatelským kanálem je e-mail. Vlastní frontend neposkytuje hodnotu potřebnou ke splnění základních ani pokročilých funkcí.

### Jak UI validuje vstupy a synchronizuje serverové chyby?

- ID: form_validation (doplňkové)
- Stav: **PŘEDPOKLAD**

Aplikace nemá vlastní webové formuláře. Uživatel odesílá dotaz prostřednictvím e-mailového klienta.

Validace probíhá na backendu:

1. FastAPI a Pydantic validují interní HTTP požadavky, datové typy a povinné parametry.
2. Gmail Adapter kontroluje strukturu MIME zprávy, identifikátory a e-mailové hlavičky.
3. Attachment Validator ověřuje PDF, MP3, WAV, JPEG a PNG podle MIME typu, signatury, velikosti a technických limitů.
4. EmailOrchestrator považuje příchozí e-mail, přílohy a externí informace za nedůvěryhodné.
5. Gemini vrací strukturovaný návrh odpovědi, který backend validuje před odesláním.

Zpracování serverových chyb:
- Neplatný vstup: odmítnutí přílohy, bezpečná odpověď nebo NEEDS_REVIEW.
- Dočasná chyba: RETRY_PENDING a kontrolovaný retry.
- Neobnovitelná chyba: FAILED.
- Nejasný výsledek odeslání: DELIVERY_UNKNOWN.

Pravdivý stav zpracování uchovává PostgreSQL. Uživateli se výsledek předává prostřednictvím e-mailu, nikoliv synchronizací frontendového formuláře.

### Jak se spravuje lokální/server state a cache invalidation?

- ID: state_management (doplňkové)
- Stav: **PŘEDPOKLAD**

STATE MANAGEMENT – REPLY MCFLY

Aplikace nemá vlastní frontend, proto nepoužívá React state, Redux ani jiný klientský state management.

1. Serverový stav
- Cloud SQL PostgreSQL je Source of Truth pro interní stav zpracování.
- email_jobs uchovává stav jednotlivých e-mailů.
- email_outbox eviduje připravené a odeslané odpovědi.
- mailbox_sync_state uchovává Gmail historyId a synchronizační lease.

2. Externí stav
- Gmail je Source of Truth pro e-mailové zprávy, přílohy a historii vláken.
- Conversation History načítá relevantní historii přímo z Gmail Threads API.

3. Lokální stav Workeru
- Worker uchovává dočasný kontext pouze během zpracování konkrétní úlohy.
- Zahrnuje načtenou zprávu, přílohy, historii a vybrané RAG/Web Search informace.
- Po dokončení se dočasná data odstraní.
- Kritický stav nesmí existovat pouze v paměti Workeru.

4. Cache
- Pro PoC nepoužíváme Redis ani jinou distribuovanou cache.
- RAG embeddingy jsou persistentně uložené v PostgreSQL.
- Dočasný AI kontext se nesdílí mezi jednotlivými úlohami.

5. Cache invalidation
- Při dokončení úlohy se zahodí její dočasný kontext.
- Při aktualizaci RAG dokumentu se aktualizují příslušné chunks a embeddingy.
- Gmail historie se pro nové zprávy opět načítá podle aktuálního threadId.
- Synchronizační checkpoint se aktualizuje až po bezpečném uložení změn.

Tím zamezujeme použití zastaralé historie a zároveň nepotřebujeme složitou cache infrastrukturu.

### Jaké viewporty a zařízení musí být podporované?

- ID: responsive_design (doplňkové)
- Stav: **PŘEDPOKLAD**

RESPONSIVE DESIGN – REPLY MCFLY

Aplikace nemá vlastní webové ani mobilní uživatelské rozhraní.

1. Podporované prostředí
- Desktopové e-mailové klienty.
- Webové e-mailové klienty.
- Mobilní e-mailové aplikace.
- Gmail a další klienty podporující standardní e-mailovou komunikaci.

2. Uživatelská komunikace
- Uživatel odesílá e-mail na dedikovanou Gmail adresu.
- Aplikace zpracuje obsah a podporované přílohy.
- Odpověď doručí do původního e-mailového vlákna.
- Vzhled e-mailového klienta spravuje jeho poskytovatel.

3. Výstupní formát
- Pro první verzi preferujeme text/plain.
- Krátké odstavce a přehledná struktura odpovědi.
- Bez vlastních interaktivních HTML prvků.
- Bez závislosti na šířce obrazovky.

4. Viewporty
- Nedefinujeme vlastní breakpointy pro mobil, tablet ani desktop.
- Responsivitu e-mailového klienta zajišťuje jeho poskytovatel.
- Není vyžadováno testování vlastního CSS layoutu.

5. Ověření
- Zobrazení odpovědi v Gmail Web.
- Zobrazení odpovědi v mobilním Gmail klientu.
- Kontrola čitelnosti textu, odkazů a zachování původního vlákna.

Pokud vznikne vlastní administrativní UI nebo HTML e-mailová šablona, požadavky na responsive design budou řešeny samostatně.

### Jak ověříš ovládání klávesnicí a čtečkou?

- ID: frontend_accessibility (doplňkové)
- Stav: **PŘEDPOKLAD**

FRONTEND ACCESSIBILITY – REPLY MCFLY

Reply McFly nemá vlastní webové uživatelské rozhraní. Ovládání klávesnicí a kompatibilitu se čtečkami obrazovky primárně zajišťuje používaný e-mailový klient.

1. Přístupnost uživatelského rozhraní
- Uživatel komunikuje prostřednictvím Gmailu nebo jiného e-mailového klienta.
- Aplikace nevytváří vlastní navigaci, formuláře ani interaktivní komponenty.
- Přístupnost ovládacích prvků závisí na použitém klientovi.

2. Přístupnost generovaných odpovědí
- Preferujeme text/plain.
- Používáme srozumitelný jazyk a logickou strukturu.
- Odpovědi obsahují krátké odstavce.
- Důležité informace nejsou sdělovány pouze barvou nebo vizuálním formátováním.
- Odkazy mají být textově srozumitelné.

3. Zpracování multimodálních příloh
- Gemini může interpretovat textové, obrazové a audio informace.
- Pokud se odpověď opírá o obrázek nebo audio, relevantní informace se vyjádří také textově.

4. Ověření
- Přečtení výsledného e-mailu čtečkou obrazovky.
- Kontrola srozumitelného pořadí informací.
- Kontrola čitelnosti na desktopu a mobilním zařízení.
- Ověření, že odpověď nevyžaduje interaktivní HTML prvky.

Formální WCAG audit vlastní aplikace není pro současné PoC relevantní, protože neprovozujeme vlastní frontend. Přístupnost generovaného obsahu však zůstává důležitá.

### Jaké jsou cíle velikosti bundle, LCP/INP či odezvy UI?

- ID: frontend_performance (doplňkové)
- Stav: **PŘEDPOKLAD**

FRONTEND PERFORMANCE – REPLY MCFLY

Aplikace nemá vlastní webový frontend, JavaScript bundle ani vykreslované stránky.

1. Frontend metriky
- Bundle size: nerelevantní.
- Largest Contentful Paint (LCP): nerelevantní.
- Interaction to Next Paint (INP): nerelevantní.
- Cumulative Layout Shift (CLS): nerelevantní.

2. Hlavní výkonnostní požadavek
- Celková doba od přijetí e-mailu po odeslání odpovědi musí být pod 120 sekund.
- Sledujeme end-to-end latency, p50, p95 a maximum.
- Měříme skutečný čas včetně Gmail notifikace a čekání ve frontě.

3. Výkonnost backendu
- Cloud Run Worker: aplikační deadline maximálně 100 sekund.
- Cloud Run HTTP timeout: 110 sekund.
- Cloud Tasks řídí concurrency a dispatch.
- Počet Worker instancí se upravuje podle naměřené zátěže.

4. Optimalizace AI
- Omezení počtu a velikosti příloh.
- Omezený token budget Conversation History.
- RAG pouze při relevantním dotazu.
- Web Search pouze při požadavku na aktuální veřejná data.
- Omezený počet externích API volání.
- Krátké PostgreSQL transakce.

5. Monitoring
- Gmail event latency.
- Queue waiting time.
- Attachment processing duration.
- RAG/Web Search latency.
- Gemini inference latency.
- Gmail Send latency.
- Celková end-to-end latency.

6. Testování
- Samostatné e-maily.
- E-maily s podporovanými přílohami.
- Navazující konverzace.
- Kombinované dotazy využívající více zdrojů.
- Zátěž 1, 3 a 5 současně přijatých e-mailů.

Cílem není optimalizace vykreslování UI, ale rychlé, spolehlivé a bezpečné automatické zpracování e-mailů.

### Jak otestuješ kritické flow v reálném prohlížeči?

- ID: frontend_testing (doplňkové)
- Stav: **PŘEDPOKLAD**

FRONTEND TESTING – REPLY MCFLY

Aplikace nemá vlastní webový frontend. Kritické uživatelské scénáře proto testujeme prostřednictvím Gmailu a skutečného e-mailového provozu.

1. Základní end-to-end test
- Otevřít Gmail v reálném webovém prohlížeči.
- Odeslat testovací e-mail na dedikovanou Gmail adresu.
- Ověřit automatické zpracování zprávy.
- Ověřit odpověď ve stejném Gmail vlákně.
- Změřit čas od přijetí do odeslání odpovědi.

2. Conversation History
- Odeslat více navazujících e-mailů ve stejném vlákně.
- Ověřit, že asistent používá relevantní předchozí informace.
- Odeslat samostatné vlákno a ověřit izolaci kontextu.

3. Multimodální přílohy
- Test PDF, MP3, WAV, JPEG a PNG.
- Ověřit správnou interpretaci obsahu.
- Testovat neplatné a nadlimitní přílohy.

4. RAG
- Odeslat dotaz na fiktivní produkt.
- Ověřit odpověď podle schváleného dokumentu.
- Ověřit, že model nevymýšlí chybějící fakta.

5. Live Web Search
- Odeslat dotaz na aktuální veřejnou informaci.
- Ověřit použití aktuálního zdroje.
- Testovat selhání vyhledávání.

6. Chybové scénáře
- Opakovaná notifikace.
- Dočasný výpadek API.
- Restart Workeru.
- Nejasný výsledek odeslání.

7. Automatizace
- Backendové testy pomocí pytest.
- Integrační testy se skutečnými cloudovými službami.
- Browser testy lze použít pouze pro kontrolu uživatelského zobrazení v Gmailu.

Není potřeba budovat rozsáhlou Playwright/Cypress infrastrukturu pro vlastní frontend, protože žádný vlastní webový frontend neexistuje.

### Jak bude fungovat záchyt chyb a zobrazení incident ID?

- ID: frontend_error_handling (doplňkové)
- Stav: **PŘEDPOKLAD**

ERROR HANDLING A INCIDENT ID – REPLY MCFLY

Aplikace nemá vlastní webové UI. Chybové stavy jsou řízeny backendem a evidovány pomocí Cloud Logging, Cloud Monitoring a PostgreSQL.

1. Identifikace chyby
- Každé zpracování má unikátní job_id.
- Logy obsahují correlation_id a technický error_code.
- Při incidentu lze dohledat průběh konkrétní úlohy.

2. Chybové stavy
- RETRY_PENDING – dočasná chyba.
- FAILED – neobnovitelná chyba nebo vyčerpání pokusů.
- NEEDS_REVIEW – nutná ruční kontrola.
- DELIVERY_UNKNOWN – nejasný výsledek Gmail Send.
- SKIPPED – zpráva byla bezpečně přeskočena.

3. Zobrazení správci
- Cloud Logging zobrazuje události podle job_id/correlation_id.
- Cloud Monitoring sleduje chybovost a latenci.
- Správce může podle identifikátoru dohledat technickou příčinu.

4. Komunikace uživateli
- Pokud lze bezpečně odpovědět, aplikace odešle srozumitelnou informaci o problému.
- U neplatné přílohy může požádat o zaslání podporovaného souboru.
- Pokud není jisté, zda původní odpověď odešla, další e-mail se automaticky neposílá.
- Interní technické detaily a stack trace se uživateli nezobrazují.

5. Incident ID
- Pro PoC použijeme job_id jako hlavní identifikátor zpracování.
- Při potřebe lze vytvořit samostatné incident_id navázané na job_id.
- Identifikátory nesmějí odhalovat obsah e-mailu ani osobní údaje.

6. Bezpečnost
- Logy neobsahují těla e-mailů, přílohy ani OAuth tokeny.
- Chybové zprávy neprozrazují interní credentials.
- Přístup k diagnostice omezuje Google IAM.

CÍL:
Umožnit dohledání a řešení incidentu bez vlastního frontendového error dashboardu.

### Kde se frontend hostuje, jak se verzují assety a CSP?

- ID: frontend_deploy (doplňkové)
- Stav: **PŘEDPOKLAD**

FRONTEND DEPLOYMENT – REPLY MCFLY

Reply McFly nemá vlastní webový frontend, proto nevyžaduje frontend hosting, CDN ani správu statických webových assetů.

1. Hosting
- Uživatelské rozhraní poskytuje Gmail nebo jiný e-mailový klient.
- Aplikace nehostuje vlastní HTML stránky.
- Backend běží v Google Cloud Run.

2. Deployment aplikace
- Cloud Run Ingress a Worker používají jeden Docker image.
- Zdrojový kód a konfigurace jsou verzované v Git repozitáři.
- Nasazení využívá Cloud Run revize.
- PostgreSQL změny jsou spravované pomocí Alembic migrací.

3. Verzování frontend assetů
- Není relevantní, protože nevytváříme JavaScript/CSS bundle.
- Nepoužíváme statické assety, frontend build ani CDN.

4. Content Security Policy (CSP)
- Vlastní webové stránky nejsou poskytovány.
- CSP pro vlastní frontend proto není požadována.
- Bezpečnost backendu zajišťují IAM/OIDC, HTTPS/TLS a serverová validace.

5. E-mailové odpovědi
- Preferovaný formát je text/plain.
- Nepoužíváme externí skripty ani interaktivní HTML komponenty.
- Odpovědi zachovávají správné MIME a Gmail threading hlavičky.

6. Budoucí rozšíření
- Pokud vznikne vlastní administrativní UI, bude nutné vybrat hosting, frontend framework, verzování assetů a CSP.
- Rozšíření bude zdokumentováno samostatným ADR.

DŮVOD:
Samostatný frontend hosting není pro e-mailového AI asistenta potřebný a zvýšil by provozní i bezpečnostní složitost.

## 10 · Backend LLD a struktura repozitáře

*Cíl:* Vývojář musí vědět, které moduly existují a co dělají.

*Gate:* Z návrhu jde implementovat nejmenší vertikální slice bez domýšlení hranic.

### Jaký backend runtime/framework a konkrétní verzi zvolíš?

- ID: backend_language (povinné)
- Stav: **PŘEDPOKLAD**

BACKEND TECHNOLOGIE – REPLY MCFLY

1. Runtime a framework
- Python 3.12 – výchozí runtime pro PoC.
- FastAPI – framework pro HTTP API.
- Uvicorn – ASGI server pro provoz v Cloud Run.
- Pydantic v2 – validace požadavků, konfigurace a strukturovaných AI výstupů.

2. Google integrace
- google-genai – komunikace s Gemini přes Vertex AI.
- google-api-python-client – Gmail API a Gmail Threads API.
- google-auth a google-auth-oauthlib – autentizace a Gmail OAuth 2.0.
- Google Cloud klientské knihovny – Cloud Tasks, Secret Manager a další potřebné služby.

3. Databáze
- SQLAlchemy 2.x – databázová aplikační vrstva.
- psycopg 3 – PostgreSQL driver.
- Alembic – verzování databázového schématu.
- pgvector – RAG embeddingy a podobnostní vyhledávání.

4. Zpracování příloh
- PyMuPDF – kontrola PDF.
- Pillow – kontrola JPEG/PNG.
- FFmpeg/ffprobe – validace délky a parametrů MP3/WAV.
- Gemini – multimodální interpretace obsahu.

5. AI orchestrace
- Vlastní deterministický EmailOrchestrator.
- Rozhraní WorkflowRunner pro budoucí rozšíření.
- LangChain, LangGraph ani CrewAI nejsou v první verzi vyžadovány.
- Při výrazném rozšíření workflow lze zavést LangGraph prostřednictvím nové implementace WorkflowRunner.

6. Deployment
- Docker image obsahující Python aplikaci.
- Dvě Cloud Run služby ze stejného image.
- Docker Compose pro lokální vývoj.
- pytest pro automatizované testování.

DŮVOD VÝBĚRU:
Jednoduchý Python ekosystém, nativní integrace s Google Cloud, přehledný vývoj, snadné testování a možnost budoucího rozšíření.

Přesné patch verze knihoven budou uzamčeny v dependency lock souboru po ověření kompatibility. Python 3.12 a uvedené hlavní verze jsou návrhovou volbou, nikoliv výsledkem otestovaného deploymentu.

### Jak bude vypadat struktura repozitáře a moduly?

- ID: module_structure (povinné)
- Stav: **PŘEDPOKLAD**

STRUKTURA REPOZITÁŘE – REPLY MCFLY

Jeden Git repozitář a jeden Docker image pro Cloud Run Ingress a Worker.

reply-mcfly/
  src/reply_mcfly/
    api/
      ingress.py
      worker.py
      schemas.py

    application/
      gmail_sync_service.py
      email_processing_service.py
      email_orchestrator.py
      maintenance_service.py
      reply_service.py

    domain/
      models.py
      states.py
      policies.py
      errors.py

    ports/
      gmail.py
      database.py
      task_queue.py
      llm.py
      embeddings.py
      web_search.py
      workflow.py

    adapters/
      gmail_adapter.py
      postgres_adapter.py
      cloud_tasks_adapter.py
      gemini_adapter.py
      google_search_adapter.py

    capabilities/
      attachments/
        validator.py
        processor.py
      thread/
        provider.py
      rag/
        provider.py
        indexer.py
      web_search/
        provider.py

    prompts/
      system_prompt.py

    config/
      settings.py

  migrations/
  tests/
    unit/
    integration/
    e2e/
    security/

  infra/
    gcp/

  docs/
    architecture/
    adr/
    operations/

  Dockerfile
  docker-compose.yml
  pyproject.toml
  .env.example
  README.md

PRAVIDLA ZÁVISLOSTÍ:
- api/ přijímá HTTP požadavky a předává je application/.
- application/ koordinuje use cases.
- domain/ obsahuje pravidla nezávislá na cloudu.
- ports/ definují rozhraní externích závislostí.
- adapters/ implementují komunikaci s Gmail, Gemini, PostgreSQL a Cloud Tasks.
- capabilities/ obsahují samostatné AI schopnosti.
- prompts/ uchovává verzované AI instrukce.

WorkflowRunner:
- Definuje rozhraní pro vykonání AI workflow.
- První implementací je vlastní EmailOrchestrator.
- Budoucí LangGraph implementace může využívat existující porty.

ARCHITEKTONICKÝ PRINCIP:
Business logika nezávisí přímo na Google SDK. SDK jsou zapouzdřena v adaptérech.

Nové AI schopnosti lze doplnit bez změny příjmu Gmail notifikací, Cloud Tasks front nebo mechanismu odesílání odpovědí.

Konkrétní názvy Python souborů představují implementační návrh.

### Jaké application services orchestruji use case?

- ID: app_services (povinné)
- Stav: **PŘEDPOKLAD**

APPLICATION SERVICES – REPLY MCFLY

1. GmailSyncService
Odpovědnost:
- Převzetí synchronizační úlohy.
- Atomická rezervace synchronizace schránky.
- Načtení změn přes Gmail History API.
- Filtrování nových nepřečtených zpráv.
- Deduplikace pomocí PostgreSQL.
- Uložení checkpointu historyId.
- Vytvoření úloh v Cloud Tasks Process Queue.

2. EmailProcessingService
Odpovědnost:
- Převzetí konkrétního email job.
- Atomická rezervace zpracování.
- Načtení zprávy a příloh.
- Spuštění validačních pravidel.
- Zavolání WorkflowRunner / EmailOrchestrator.
- Předání výsledku ReplyService.
- Evidence výsledného stavu.

3. EmailOrchestrator / WorkflowRunner
Odpovědnost:
- Řízení AI workflow.
- Výběr relevantních kontextových zdrojů.
- Conversation History pro navazující komunikaci.
- RAG pro interní produktová fakta.
- Web Search pro aktuální veřejné informace.
- Sestavení kontextu pro Gemini.
- Generování strukturovaného návrhu odpovědi.

4. ReplyService
Odpovědnost:
- Validace AI odpovědi.
- Kontrola povoleného příjemce.
- Příprava Gmail threading hlaviček.
- Uložení outbox záznamu.
- Odeslání přes Gmail API.
- Ověření odeslání.
- Bezpečné řešení DELIVERY_UNKNOWN.

5. MaintenanceService
Odpovědnost:
- Obnova Gmail Watch.
- Kontrola nedokončených úloh.
- Recovery expirovaných rezervací.
- Opětovné zařazení chybějících úloh.
- Řízená synchronizace při neplatném historyId.

6. KnowledgeIndexingService
Odpovědnost:
- Import 1–3 schválených RAG dokumentů.
- Rozdělení dokumentů na chunks.
- Generování embeddingů.
- Uložení do PostgreSQL/pgvector.
- Aktualizace verzí znalostní báze.

VZÁJEMNÉ VZTAHY:
- GmailSyncService zjišťuje a eviduje zprávy.
- EmailProcessingService řídí životní cyklus email job.
- EmailOrchestrator připravuje AI odpověď.
- ReplyService bezpečně odesílá.
- MaintenanceService zajišťuje obnovu po chybě.
- KnowledgeIndexingService připravuje RAG data mimo hlavní email workflow.

Každá application service používá porty a nepřistupuje přímo ke konkrétním cloudovým SDK.

### Jaká business pravidla patří do domain layer?

- ID: domain_rules (povinné)
- Stav: **PŘEDPOKLAD**

DOMAIN RULES – REPLY MCFLY

Domain layer obsahuje pravidla zpracování e-mailů nezávislá na FastAPI, Gmail SDK, Gemini a Google Cloud infrastruktuře.

1. Identita a deduplikace
- Každá zpráva je jednoznačně identifikována kombinací mailbox_id a gmail_message_id.
- Jedna příchozí zpráva smí vytvořit maximálně jednu automatickou odpověď.
- Duplicitní událost nesmí vytvořit další zpracování ani odeslání.

2. Stavový automat
- Hlavní stavy: QUEUED → PROCESSING → READY_TO_SEND → SENDING → SENT.
- Doplňkové stavy: RETRY_PENDING, FAILED, NEEDS_REVIEW, DELIVERY_UNKNOWN a SKIPPED.
- Jsou povoleny pouze definované stavové přechody.
- Stav SENT vyžaduje potvrzené nebo ověřené odeslání.

3. Vlastnictví úloh
- Jednu úlohu smí aktivně zpracovávat pouze jeden Worker.
- Rezervace používá lease s expirací.
- Zastaralý Worker nesmí změnit stav úlohy vlastněné jiným Workerem.
- Zprávy stejného vlákna musí respektovat pořadí konverzace.

4. Pravidla výběru zpráv
- Zpracovávají se nové příchozí zprávy, které byly při detekci nepřečtené.
- Vlastní odeslané zprávy a známé automatické odpovědi se ignorují.
- Zabraňujeme automatickým e-mailovým smyčkám.

5. Conversation History
- Kontext smí obsahovat pouze zprávy aktuálního gmail_thread_id.
- Historie zachovává chronologické pořadí.
- Kontext je omezen počtem zpráv nebo token budgetem.

6. RAG a Web Search
- RAG používá pouze schválené znalostní dokumenty.
- Nepodložená produktová fakta se nesmějí vymýšlet.
- Web Search se používá pouze při potřebě aktuálních veřejných informací.
- Soukromé e-mailové informace nesmějí být předány do veřejného vyhledávání.

7. Přílohy
- Povolené formáty: PDF, MP3, WAV, JPEG a PNG.
- Platí definované limity počtu, velikosti a obsahu.
- Nepodporovaný nebo neplatný soubor musí být bezpečně odmítnut.

8. Odesílání odpovědí
- Příjemce určuje backend, nikoliv Gemini.
- Odpověď musí zachovat původní Gmail vlákno.
- Při DELIVERY_UNKNOWN se nesmí automaticky opakovat odeslání bez ověření.

Domain layer definuje pravidla a rozhodnutí. Application layer koordinuje jejich vykonání. Infrastructure adapters provádějí konkrétní operace vůči Gmail API, PostgreSQL a Vertex AI.

### Jaká rozhraní/DTO/typy musí existovat?

- ID: interfaces (povinné)
- Stav: **PŘEDPOKLAD**

INTERFACES A DTO – REPLY MCFLY

Použijeme Python Protocol/ABC pro porty, Pydantic v2 pro API kontrakty a dataclasses nebo typované modely pro doménové objekty.

1. Externí porty
- GmailPort – čtení zpráv, příloh, vláken, Gmail History a odesílání.
- EmailJobRepository – evidence úloh, stavů, lease a deduplikace.
- MailboxSyncRepository – synchronizační checkpointy a rezervace.
- OutboxRepository – příprava, evidence a kontrola odesílání.
- TaskQueuePort – vytvoření synchronizačních a zpracovatelských úloh.
- LLMPort – generování strukturované odpovědi.
- EmbeddingPort – generování embeddingů.
- KnowledgeRepository – ukládání a RAG retrieval.
- WebSearchPort – získávání aktuálních veřejných informací.

2. AI orchestrace
- WorkflowRunner – spuštění kompletního AI workflow.
- ThreadContextProvider – historie aktuálního vlákna.
- RAGProvider – relevantní znalostní úseky.
- WebSearchProvider – veřejné aktuální výsledky.
- AttachmentProcessor – validace a příprava příloh.

3. Hlavní DTO
- GmailNotification – email_address, history_id.
- SyncTask – mailbox_id.
- ProcessTask – job_id.
- EmailMessage – identifikátory, odesílatel, příjemce, předmět, tělo a přílohy.
- Attachment – název, MIME typ, velikost a obsah/referenci.
- ThreadContext – zprávy stejného vlákna.
- KnowledgeChunk – obsah, dokument a zdroj.
- WebSearchResult – text, URL, zdroj a dostupné datum.
- ProcessingContext – relevantní kontext pro AI.
- ReplyDraft – strukturovaný návrh odpovědi.
- EmailJob – identita a stav zpracování.
- OutboxEntry – příjemce, RFC Message-ID a stav odeslání.

4. Doménové typy
- EmailJobStatus – povolené stavy úloh.
- OutboxStatus – stavy odesílání.
- AttachmentType – povolené formáty.
- ErrorCode – klasifikace chyb.
- SourceType – EMAIL, THREAD, RAG, WEB.

5. Pravidla
- Application layer závisí na portech, nikoliv na konkrétních SDK.
- Implementace portů jsou v adapters/.
- DTO nesmějí umožnit modelu libovolně změnit příjemce nebo threadId.
- Každé rozhraní musí mít jednotkové testy a odpovídající integrační test adaptéru.

Rozhraní WorkflowRunner umožní v budoucnu nahradit vlastní EmailOrchestrator například LangGraph implementací bez změny hlavního vstupního a výstupního kontraktu.

Konkrétní názvy DTO a portů jsou návrhem implementace a mohou se při vývoji zpřesnit.

### Jaký je úplně první vertikální slice UI/API/DB/test/deploy?

- ID: first_slice (povinné)
- Stav: **PŘEDPOKLAD**

FIRST VERTICAL SLICE – REPLY MCFLY

Cíl:
Prokázat kompletní funkční řetězec od přijetí e-mailu po automatickou odpověď ve stejném Gmail vlákně.

Rozsah prvního vertikálního slice:

1. UI
- Žádný vlastní frontend.
- Použijeme dedikovanou Gmail schránku a testovací e-mailový účet.

2. API a backend
- Python 3.12 + FastAPI.
- Cloud Run Ingress: POST /events/gmail.
- Cloud Run Worker: POST /tasks/sync a POST /tasks/process.
- Gmail OAuth 2.0 a Gmail API.
- Gmail Watch → Pub/Sub → Cloud Tasks.
- Základní EmailOrchestrator s Gemini Adapterem.
- ReplyService pro odeslání do původního vlákna.

3. Databáze
- Cloud SQL PostgreSQL.
- První Alembic migrace.
- Tabulky mailbox_sync_state, email_jobs a email_outbox.
- Deduplikace pomocí UNIQUE(mailbox_id, gmail_message_id).
- Atomické rezervace a evidence výsledku odeslání.

4. AI
- Zpracování textového e-mailu.
- Volání Gemini přes Google Gen AI SDK.
- Strukturovaný návrh odpovědi.
- Backendová validace před odesláním.

5. Deployment
- Jeden Docker image.
- Dvě Cloud Run služby: Ingress a Worker.
- Pub/Sub topic a push subscription.
- Cloud Tasks Sync Queue a Process Queue.
- Secret Manager pro Gmail OAuth.
- Cloud Logging pro diagnostiku.

6. Testy
- Odeslání nového nepřečteného e-mailu.
- Automatické spuštění bez manuálního zásahu.
- Vygenerování relevantní odpovědi.
- Ověření správného Gmail threadId a reply hlaviček.
- Opakovaná notifikace nesmí vytvořit druhou odpověď.
- Simulace dočasné chyby API.
- Změření skutečné end-to-end latence pod 120 sekund v testovaných podmínkách.

7. Akceptační kritérium
Testovací e-mail spustí automatický cloudový workflow, který bezpečně odešle jednu odpověď do původního vlákna. Výsledek a latence jsou doloženy logy.

NÁSLEDUJÍCÍ INKREMENTY:
- Conversation History.
- Validace a interpretace PDF, MP3, WAV, JPEG a PNG.
- RAG nad 1–3 fiktivními dokumenty.
- Live Web Search.
- Kombinované testy všech tří schopností.
- Bezpečnostní a zátěžové testy.

První vertikální slice je cílový implementační milník, nikoliv již dokončená funkcionalita.

### Jak mapuješ doménové chyby na API a UI?

- ID: error_taxonomy (doplňkové)
- Stav: **PŘEDPOKLAD**

ERROR TAXONOMY – REPLY MCFLY

Aplikace používá jednotnou klasifikaci doménových chyb oddělenou od HTTP vrstvy a konkrétních cloudových SDK.

1. Doménové chyby
- INVALID_EMAIL – neplatná struktura e-mailu.
- UNSUPPORTED_ATTACHMENT – nepodporovaný typ přílohy.
- ATTACHMENT_LIMIT_EXCEEDED – překročené limity příloh.
- THREAD_CONTEXT_ERROR – nelze bezpečně načíst historii vlákna.
- KNOWLEDGE_NOT_FOUND – RAG neobsahuje požadované informace.
- WEB_SEARCH_UNAVAILABLE – aktuální informace nelze ověřit.
- INVALID_AI_RESPONSE – neplatný nebo nepodložený výstup Gemini.
- DUPLICATE_MESSAGE – zpráva je již evidována.
- INVALID_STATE_TRANSITION – nepovolený stavový přechod.
- DELIVERY_UNKNOWN – nejasný výsledek odeslání.

2. Integrační chyby
- GMAIL_API_ERROR
- GEMINI_API_ERROR
- DATABASE_UNAVAILABLE
- DEPENDENCY_TIMEOUT
- RATE_LIMITED
- AUTHENTICATION_FAILED
- AUTHORIZATION_FAILED

3. Mapování na HTTP API
- 400/422 – neplatný request nebo jeho struktura.
- 401/403 – neplatná autentizace nebo oprávnění.
- 404 – neexistující interní úloha.
- 429 – překročení aplikačního limitu, pokud je zaveden.
- 500 – neočekávaná interní chyba.
- 503 – dočasně nedostupná závislost.
- 504 – překročený aplikační timeout.

4. Mapování na stav úlohy
- Dočasná chyba → RETRY_PENDING.
- Neobnovitelná chyba → FAILED.
- Nelze bezpečně odpovědět → NEEDS_REVIEW.
- Nejasné odeslání → DELIVERY_UNKNOWN.
- Nepodporovaná/ignorovaná zpráva → SKIPPED.
- Úspěšně dokončená úloha → SENT.

5. Uživatelské rozhraní
- Aplikace nemá vlastní webové UI.
- Pokud lze bezpečně odpovědět, uživatel obdrží srozumitelný e-mail s informací o problému.
- Technické detaily se uživateli neposílají.
- Pokud je výsledek odeslání nejasný, automaticky se další zpráva neposílá.

6. Logování
- job_id, correlation_id, error_code, component, retryable.
- Bez těla e-mailu, příloh a přístupových údajů.

DŮLEŽITÉ:
HTTP 2xx znamená úspěšné dokončení konkrétní HTTP operace. U trvale odmítnutého e-mailu může endpoint vrátit 2xx po bezpečném uložení stavu SKIPPED nebo NEEDS_REVIEW. Dočasné chyby umožňují retry pomocí Cloud Tasks.

Konkrétní kódy a mapování HTTP odpovědí jsou implementační návrh.

### Jak řídíš background joby, retry/dedup, timeouts a zrušení?

- ID: background_jobs (doplňkové)
- Stav: **PŘEDPOKLAD**

BACKGROUND JOB MANAGEMENT – REPLY MCFLY

Používáme Google Cloud Tasks pro asynchronní zpracování a PostgreSQL jako autoritativní úložiště stavů.

1. Typy background jobs
- Sync Job – synchronizace Gmail schránky.
- Process Job – zpracování konkrétního příchozího e-mailu.
- Maintenance Job – obnova Gmail Watch a recovery nedokončených úloh.
- RAG Indexing Job – řízený import znalostních dokumentů mimo hlavní workflow.

2. Cloud Tasks fronty
- reply-mcfly-sync – maximálně 1 současná synchronizace schránky.
- reply-mcfly-process – maximálně 3 současné zpracovatelské úlohy.
- Při vyšší zátěži zůstávají úlohy ve frontě.

3. Stavový automat
- QUEUED → PROCESSING → READY_TO_SEND → SENDING → SENT.
- RETRY_PENDING – dočasná chyba.
- FAILED – vyčerpané pokusy.
- NEEDS_REVIEW – nutná kontrola.
- DELIVERY_UNKNOWN – nejasný výsledek odeslání.
- SKIPPED – ignorovaná nebo nepodporovaná zpráva.

4. Deduplikace
- UNIQUE(mailbox_id, gmail_message_id).
- Atomická rezervace úlohy pomocí PostgreSQL.
- Lease s expirací.
- UNIQUE(job_id) v email_outbox.
- Kontrola stavu před opakovaným zpracováním nebo odesláním.

5. Retry
- Cloud Tasks používá exponential backoff.
- Výchozí aplikační limit: maximálně 3 pokusy.
- Retry pouze pro vhodné dočasné chyby.
- Gmail Send se nesmí slepě opakovat.
- DELIVERY_UNKNOWN vyžaduje kontrolu Gmailu.

6. Timeouty
- Cloud Run Worker HTTP timeout: 110 sekund.
- Aplikační deadline: maximálně 100 sekund.
- Externí API mají kratší timeouty podle zbývajícího časového rozpočtu.
- Celkový cíl: odpověď do 120 sekund od přijetí e-mailu.

7. Zrušení úlohy
- Zrušení se řídí stavem v PostgreSQL.
- Pokud úloha ještě neběží, označí se jako SKIPPED nebo odpovídající terminální stav.
- Běžící Worker musí před kritickou operací ověřit aktuální stav.
- Zrušení Cloud Tasks úlohy samo o sobě nezastavuje již běžící HTTP zpracování.
- Po zahájení Gmail Send nelze předpokládat bezpečné zrušení odeslání.

8. Recovery
- Cloud Scheduler vyhledává nedokončené úlohy.
- Expirované lease umožňují bezpečné převzetí.
- Při ztracené Gmail notifikaci proběhne řízená synchronizace.

Cloud Tasks poskytuje at-least-once delivery. Bezpečné zpracování a ochranu před duplicitami zajišťuje aplikace pomocí PostgreSQL.

### Kde jsou hranice adaptérů a externí závislosti?

- ID: dependency_injection (doplňkové)
- Stav: **PŘEDPOKLAD**

DEPENDENCY INJECTION – REPLY MCFLY

Používáme Ports & Adapters a jednoduchý dependency injection mechanismus v Pythonu/FastAPI.

1. Domain Layer
- Obsahuje doménové modely, stavový automat a bezpečnostní pravidla.
- Nezávisí na Gmail SDK, Gemini, SQLAlchemy ani Google Cloud knihovnách.

2. Application Layer
- GmailSyncService.
- EmailProcessingService.
- EmailOrchestrator / WorkflowRunner.
- ReplyService.
- MaintenanceService.
- KnowledgeIndexingService.

Application services používají pouze definovaná rozhraní (ports).

3. Ports
- GmailPort.
- EmailJobRepository.
- MailboxSyncRepository.
- OutboxRepository.
- TaskQueuePort.
- LLMPort.
- EmbeddingPort.
- KnowledgeRepository.
- WebSearchPort.
- WorkflowRunner.

4. Adapters
- GmailAdapter – Google API Python Client.
- PostgreSQLAdapter – SQLAlchemy + psycopg.
- CloudTasksAdapter – Google Cloud Tasks SDK.
- GeminiAdapter – Google Gen AI SDK.
- GoogleSearchAdapter – Google Search grounding přes podporované Gemini API.

5. Dependency Injection
- FastAPI Depends pro HTTP endpointy.
- Centralizovaný composition root sestavuje konkrétní implementace.
- Konfigurace se načítá z prostředí a Secret Manageru.
- Produkční prostředí používá skutečné adaptéry.
- Testovací prostředí používá fake/mock adaptéry.

6. Rozšiřitelnost
- Nový kontextový modul implementuje definované rozhraní.
- EmailOrchestrator jej zapojí bez změny cloudových front a Gmail integrace.
- WorkflowRunner umožňuje později použít LangGraph jako alternativní orchestrátor.
- Nepotřebujeme samostatný dependency injection framework.

7. Testování
- Unit testy používají mockované porty.
- Integrační testy ověřují konkrétní adaptéry.
- Dependency overrides umožňují izolovat externí API během testování.

CÍL:
Oddělit business logiku od externích technologií, zjednodušit testování a umožnit budoucí změnu poskytovatele nebo orchestrace.

### Jaké používáš názvosloví, lint, format, typování a review?

- ID: code_conventions (doplňkové)
- Stav: **PŘEDPOKLAD**

CODE CONVENTIONS – REPLY MCFLY

1. Jazyk a standardy
- Python 3.12.
- Dodržování PEP 8 a moderních Python conventions.
- Type hints pro veřejná rozhraní, services a DTO.
- Pydantic v2 pro validaci API dat.

2. Názvosloví
- Moduly a funkce: snake_case.
- Třídy a DTO: PascalCase.
- Konstanty: UPPER_SNAKE_CASE.
- Privátní implementační metody: prefix _.
- Asynchronní funkce: async def, pokud skutečně používají async I/O.
- Názvy musí vyjadřovat odpovědnost komponenty.

3. Formátování a lint
- Ruff pro linting a formátování.
- Konzistentní importy a styl kódu.
- Automatické kontroly před commitem a v CI.
- Nepoužívat nevyužité importy, proměnné ani zbytečné závislosti.

4. Typová kontrola
- Mypy nebo Pyright pro statickou analýzu.
- Přednost mají explicitní typy na hranicích modulů.
- Omezovat použití Any.
- DTO a porty mají jasně definované kontrakty.

5. Architektonická pravidla
- Domain layer nesmí importovat cloudové SDK.
- Application layer komunikuje přes ports.
- Adapters obsahují implementace externích integrací.
- API endpointy nemají obsahovat business logiku.
- AI prompty a konfigurace se verzují.

6. Testování
- pytest pro unit/integration/e2e testy.
- Mockované externí API v unit testech.
- Integrační testy databáze a adapterů.
- Bezpečnostní testy pro vstupy, přílohy a prompt injection.

7. Code review
- Změny se evidují pomocí Git commitů a Pull Requestů.
- Každá změna musí projít lintem, typovou kontrolou a relevantními testy.
- Bezpečnostně významné změny vyžadují kontrolu oprávnění, vstupů a práce se secrets.
- V rámci PoC jednoho vývojáře se používá checklist self-review.

8. Dokumentace
- README s postupem spuštění.
- ADR pro architektonická rozhodnutí.
- Dokumentace ports a externích integrací.
- Evidence technických omezení a známých rizik.

Konkrétní CI nástroje a pravidla review jsou návrhem a budou potvrzeny při založení repozitáře.

### Jak zapínáš/nevracíš funkce bez redeploy?

- ID: feature_flags (doplňkové)
- Stav: **PŘEDPOKLAD**

FEATURE FLAGS – REPLY MCFLY

Pro počáteční PoC používáme jednoduché feature flags pro pokročilé AI schopnosti.

1. Definované přepínače
- ENABLE_THREAD_CONTEXT – Conversation History.
- ENABLE_RAG – Retrieval-Augmented Generation.
- ENABLE_WEB_SEARCH – Live Web Search.

2. Výchozí konfigurace
- Všechny tři pokročilé funkce jsou v cílovém řešení zapnuté.
- Přepínače slouží pro izolované testování, diagnostiku a kontrolované nasazování.
- Vypnutí funkce nesmí způsobit nepodloženou odpověď, pokud je daný zdroj nezbytný.

3. Způsob konfigurace
- Počáteční konfigurace pomocí environment variables Cloud Run.
- Nastavení je verzované a dokumentované.
- Lokální vývoj používá .env.example.
- Secrets se neukládají mezi běžné feature flags.

4. Změna bez redeploy
- Cloud Run environment variables nelze změnit pro běžící revizi bez vytvoření nové revize.
- Pokud je požadováno skutečné přepínání bez redeploy, zavedeme načítání flags z PostgreSQL.
- Worker může konfiguraci načítat na začátku každé úlohy.
- Není potřeba Redis ani samostatná feature flag platforma.

5. Bezpečnost
- Feature flags mění pouze povolené aplikační schopnosti.
- Nemohou deaktivovat autentizaci, autorizaci, deduplikaci ani bezpečnostní validaci.
- Změny smí provádět pouze správce aplikace.

6. Testování
- Conversation History samostatně.
- RAG samostatně.
- Web Search samostatně.
- Kombinace všech tří schopností.
- Ověření chování při vypnutém nezbytném zdroji.

7. Budoucí rozšíření
- Při větším provozu lze zavést centralizovanou feature flag službu.
- Pro jednu dedikovanou schránku není potřebná.

DOPORUČENÍ:
Pro PoC začneme environment variables. Pokud vznikne skutečný požadavek na runtime změny bez nové Cloud Run revize, použijeme jednoduchou PostgreSQL konfiguraci.

### Jak vývojář spustí celý stack lokálně jedním postupem?

- ID: developer_setup (doplňkové)
- Stav: **PŘEDPOKLAD**

LOCAL DEVELOPER SETUP – REPLY MCFLY

Lokální vývoj používá Docker Compose a jeden aplikační repozitář.

1. Požadavky
- Git.
- Docker a Docker Compose.
- Python 3.12 pro lokální vývoj mimo kontejner.
- Testovací Gmail účet a OAuth konfigurace pro integrační testy.
- Přístup ke GCP trial projektu pro testy skutečného Gemini API.

2. Inicializace
- Naklonovat Git repozitář.
- Zkopírovat .env.example do lokálního .env.
- Doplnit pouze vývojovou konfiguraci.
- Produkční secrets neukládat do repozitáře.

3. Spuštění
- docker compose up --build

Spustí se:
- reply-mcfly-ingress – FastAPI.
- reply-mcfly-worker – stejný Docker image s jiným startovacím příkazem.
- postgres – PostgreSQL s pgvector a persistentním volume.

4. Databáze
- Spustit Alembic migrace.
- Ověřit dostupnost databáze.
- Inicializovat testovací RAG dokumenty, pokud jsou vyžadovány.

5. Lokální integrace
- Cloud Tasks lze nahradit vývojovým HTTP adaptérem nebo fake queue.
- Gmail API a Gemini lze v unit testech mockovat.
- Reálné OAuth a Vertex AI integrace se testují odděleně.
- Produkční IAM/OIDC mechanismy se ověřují v GCP, nikoliv pouze lokálně.

6. Testování
- pytest tests/unit
- pytest tests/integration
- pytest tests/security
- pytest tests/e2e podle dostupného testovacího prostředí.

7. Ověření funkčnosti
- Odeslat syntetický testovací e-mail.
- Ověřit načtení těla zprávy a příloh.
- Ověřit Conversation History.
- Ověřit RAG retrieval.
- Ověřit Web Search adaptér.
- Ověřit návrh odpovědi a bezpečné Gmail odeslání.
- Zkontrolovat databázové stavy a logy.

8. Deployment
- Build jednoho Docker image.
- Nasazení dvou Cloud Run služeb.
- Konfigurace Pub/Sub, Cloud Tasks, Cloud SQL, Secret Manager a Scheduler.
- End-to-end test v GCP trial prostředí.

CÍL:
Umožnit reprodukovatelný lokální vývoj bez nutnosti emulovat všechny Google Cloud služby.

Konkrétní Docker Compose konfigurace a příkazy budou dokončeny při implementaci. Uvedený postup je cílový developer workflow, nikoliv zatím ověřený návod.

### Kde je README, CHANGELOG, CODEOWNERS, docs a ADR?

- ID: repository_structure (doplňkové)
- Stav: **PŘEDPOKLAD**

DOKUMENTACE A STRUKTURA REPOZITÁŘE – REPLY MCFLY

Projekt používá jeden Git repozitář pro aplikační kód, infrastrukturu, testy a dokumentaci.

Navržená struktura:

reply-mcfly/
  README.md
  CHANGELOG.md
  pyproject.toml
  Dockerfile
  docker-compose.yml
  .env.example

  .github/
    CODEOWNERS
    workflows/
      ci.yml

  src/
    reply_mcfly/
      api/
      application/
      domain/
      ports/
      adapters/
      capabilities/
      prompts/
      config/

  migrations/

  tests/
    unit/
    integration/
    e2e/
    security/

  infra/
    gcp/

  docs/
    architecture/
      system-context.md
      container-diagram.md
      erd.md

    adr/
      001-architecture.md

    operations/
      deployment.md
      runbook.md
      recovery.md

    security/
      threat-model.md
      security-review.md

1. README.md
- Hlavní vstupní dokumentace projektu.
- Popis účelu a architektury.
- Požadavky na vývojové prostředí.
- Postup lokálního spuštění.
- Konfigurace Gmail OAuth a GCP.
- Spuštění testů a deployment.
- Omezení a známá rizika.

2. CHANGELOG.md
- Evidence změn mezi verzemi.
- Nové funkce, opravy a nekompatibilní změny.
- Změny API, databáze a integrací.

3. .github/CODEOWNERS
- Definuje vlastníky jednotlivých částí repozitáře.
- Pro PoC je vlastníkem AI Engineer.
- Při rozšíření týmu lze určit samostatné vlastníky backendu, AI a infrastruktury.

4. docs/architecture/
- C4 System Context diagram.
- C4 Container diagram.
- ER diagram.
- Popis toku Gmail → Pub/Sub → Cloud Tasks → Worker → Gemini → Gmail Reply.

5. docs/adr/
- Architecture Decision Records.
- ADR-001: Event-driven Modular Monolith + Ports & Adapters.
- Nová ADR vzniknou při významné změně architektury, například zavedení LangGraph nebo samostatné cache.

6. docs/operations/
- Postup nasazení do GCP.
- Monitoring a řešení provozních chyb.
- Recovery Gmail synchronizace.
- Obnova po výpadku databáze.
- Kontrola duplicit a stavů DELIVERY_UNKNOWN.

7. docs/security/
- Threat model.
- Bezpečnostní pravidla.
- Výsledky security review.
- Evidence nálezů a nápravných opatření.

8. tests/
- Unit, integration, end-to-end a security testy.
- Ověření Conversation History, RAG, Web Search, příloh a latence pod 120 sekund.

PRINCIP:
Dokumentace se verzujte společně se zdrojovým kódem. Každá významná architektonická změna musí být zaznamenána v ADR a promítnuta do diagramů.

Uvedená struktura je cílový návrh repozitáře. Současná projektová dokumentace obsahuje architekturu v1.0 a ADR-001 jako architektonické rozhodnutí; existence jednotlivých souborů v Git repozitáři zatím není ověřena.

GIT IGNORE A OCHRANA CITLIVÝCH SOUBORŮ

- .gitignore je umístěn v kořenovém adresáři repozitáře.
- Vylučuje lokální .env soubory, OAuth tokeny, GCP credentials, privátní klíče, skutečné e-maily, soukromé přílohy, logy, databázové zálohy a generované soubory.
- .env.example zůstává v Git repozitáři pouze s ukázkovými hodnotami.
- Produkční secrets jsou uloženy v Google Cloud Secret Manageru.
- Testovací PDF, MP3, WAV, JPEG a PNG lze verzovat pouze jako bezpečná syntetická data.
- .dockerignore zabraňuje kopírování citlivých a nepotřebných souborů do Docker build contextu.
- Gitleaks kontroluje možné úniky přístupových údajů.
- .gitignore nenahrazuje bezpečnostní kontrolu, protože již verzované soubory automaticky neodstraní.
- Při úniku secretu je nutné jej okamžitě revokovat, nahradit a podle potřeby odstranit z Git historie.

Git repozitář obsahuje pouze zdrojový kód, dokumentaci, databázové migrace, infrastrukturu, konfiguraci bez secrets a bezpečná syntetická testovací data.

## 11 · Prostředí, infrastruktura a CI/CD

*Cíl:* Nasazení je reprodukovatelné a přístupy nejsou v laptopu.

*Gate:* Existuje cílové prostředí, pipeline, secrets, migrace a rollback.

### Kde přesně poběží production a v jakém regionu?

- ID: hosting_provider (povinné)
- Stav: **PŘEDPOKLAD**

HOSTING A REGION – REPLY MCFLY

Poskytovatel infrastruktury: Google Cloud Platform (GCP).

Výchozí region: europe-west1 (Belgie, EU).

1. Cloud Run
- reply-mcfly-ingress – příjem Gmail/Pub/Sub notifikací.
- reply-mcfly-worker – synchronizace Gmailu a AI zpracování.
- Obě služby budou nasazeny v regionu europe-west1.

2. Cloud Tasks
- Sync Queue – synchronizace schránky.
- Process Queue – zpracování jednotlivých e-mailů.
- Fronty budou umístěny v podporovaném EU regionu.

3. Cloud SQL
- PostgreSQL + pgvector v regionu europe-west1.
- Ukládání stavů úloh, outboxu, checkpointů a RAG dokumentů.

4. Pub/Sub
- Přijímání Gmail Watch notifikací.
- Služba používá vlastní pravidla pro umístění dat; regionální omezení musí být ověřeno a případně nakonfigurováno.

5. Vertex AI Gemini
- Multimodální inference, embeddingy a Google Search grounding.
- Region a model budou vybrány podle podpory požadovaných funkcí.
- Není automaticky zaručeno, že všechny AI operace proběhnou v europe-west1.

6. Ostatní služby
- Secret Manager – OAuth credentials.
- Cloud Scheduler – údržba a recovery.
- Cloud Logging / Monitoring – provozní diagnostika.

Prostředí:
- PoC bude nasazeno do samostatného GCP projektu v rámci dostupného trial/free-tier kreditu.
- Pro účely PoC představuje toto prostředí cílový deployment, nikoliv produkční SLA prostředí.
- Samostatná produkce se stejnou architekturou může vzniknout později.

Výběr regionu je návrhový a musí být ověřen proti dostupnosti služeb, cenám, kvótám a požadavkům na umístění dat.

### Jak bude aplikace zabalená a nasazená (PaaS, VM, containers)?

- ID: deployment_strategy (povinné)
- Stav: **PŘEDPOKLAD**

DEPLOYMENT STRATEGY – REPLY MCFLY

Použijeme serverless container deployment na Google Cloud Run.

1. Architektonický model
- Event-driven Modular Monolith.
- Jeden Git repozitář.
- Jeden Docker image.
- Dvě samostatné Cloud Run služby: Ingress a Worker.
- Obě služby používají stejný aplikační kód, ale odlišnou konfiguraci a vstupní endpointy.

2. Runtime
- Python 3.12.
- FastAPI + Uvicorn.
- Google Gen AI SDK a Google Cloud SDK.
- SQLAlchemy + psycopg pro PostgreSQL.

3. Container build
- Multi-stage Docker build, pokud přinese měřitelnou výhodu.
- Minimalizovaný Python base image.
- Instalace uzamčených závislostí.
- Spuštění aplikace jako neprivilegovaný uživatel.
- Žádné secrets zabudované do image.

4. Image registry
- Google Artifact Registry.
- Image označen verzí a jednoznačným digestem.
- Stejný image se používá pro Ingress i Worker.

5. Deployment
- Docker image se sestaví a otestuje.
- Image se nahraje do Artifact Registry.
- Nasadí se Cloud Run Ingress a Worker.
- Nakonfigurují se IAM, Pub/Sub, Cloud Tasks a Secret Manager.
- Provede se smoke test a end-to-end test.

6. Cloud Run nastavení
- Ingress: max. 2 instance, concurrency 10.
- Worker: max. 3 instance, concurrency 1.
- Worker HTTP timeout: 110 sekund.
- Výchozí škálování na nulu.
- Limity lze upravit podle zátěžových testů.

7. Proč ne VM nebo Kubernetes
- Není nutná správa operačního systému ani clusteru.
- Cloud Run automaticky škáluje kontejnery.
- Nižší provozní složitost.
- Vhodné pro nepravidelné e-mailové úlohy.

8. Rollback
- Cloud Run uchovává revize služby.
- Při chybě lze přesměrovat provoz na předchozí kompatibilní revizi.
- Databázové změny používají zpětně kompatibilní Alembic migrace.

CÍL:
Jednoduchý, reprodukovatelný a škálovatelný deployment bez správy virtuálních serverů nebo Kubernetes.

### Jaká prostředí dev/test/staging/prod existují a jak se liší?

- ID: environment_matrix (povinné)
- Stav: **PŘEDPOKLAD**

ENVIRONMENT MATRIX – REPLY MCFLY

Pro první PoC používáme dvě hlavní prostředí: LOCAL a GCP PoC. Samostatné staging a production prostředí zatím nevytváříme.

1. LOCAL – vývoj
- Docker Compose.
- Python/FastAPI Ingress a Worker.
- Lokální PostgreSQL + pgvector.
- Mockované Gmail, Gemini, Web Search a Cloud Tasks adaptéry.
- Syntetické testovací e-maily a přílohy.
- Bez produkčních credentials.
- Účel: Vývoj, unit testy a základní integrační testy.

2. GCP PoC – cloudové testovací prostředí
- Samostatný Google Cloud projekt.
- Cloud Run Ingress a Worker.
- Pub/Sub + Cloud Tasks.
- Cloud SQL PostgreSQL/pgvector.
- Secret Manager a Cloud Scheduler.
- Skutečné Gmail API a Vertex AI Gemini.
- Dedikovaná testovací Gmail schránka.
- Syntetická testovací data.
- Účel: Integrační testy, end-to-end demo a měření latence.

3. STAGING – budoucí prostředí
- Není součástí počátečního PoC.
- Pokud bude potřeba, vytvoří se oddělený GCP projekt nebo izolované prostředky.
- Použije stejný Docker image a Infrastructure as Code.
- Bude sloužit pro regresní a předprodukční testy.

4. PRODUCTION – budoucí prostředí
- Není požadováno jako samostatné prostředí pro první PoC.
- Bude vyžadovat schválené zabezpečení, monitoring, zálohy a provozní pravidla.
- Použije samostatné OAuth credentials, databázi a cloudovou konfiguraci.
- Produkční data se nesmějí míchat s testovacími.

5. Rozdíly mezi prostředími
- Odlišné GCP projekty a servisní identity.
- Odlišné secrets a databáze.
- Odlišné Gmail schránky.
- Konfigurovatelné limity Cloud Run a Cloud Tasks.
- Stejná aplikační logika a verzovaný Docker image.

DŮVOD:
Pro jednoho vývojáře a omezený GCP trial rozpočet není nutné provozovat čtyři plnohodnotná prostředí. PoC vyžaduje především lokální vývoj a skutečný cloudový end-to-end test.

### Jaké kontroly musí projít PR před merge?

- ID: ci_pipeline (povinné)
- Stav: **PŘEDPOKLAD**

CONTINUOUS INTEGRATION – REPLY MCFLY

CI pipeline bude implementována pomocí GitHub Actions. Spustí se automaticky při každém Pull Requestu do hlavní větve.

1. Kontrola zdrojového kódu
- Ruff – linting a formátování Python kódu.
- Pyright nebo mypy – statická kontrola typů.
- Kontrola konzistentních importů a coding conventions.

2. Unit testy
- pytest – testování aplikační a doménové logiky.
- Mockované Gmail, Gemini, RAG a Web Search adaptéry.
- Test stavového automatu a idempotence.
- Test pravidel pro Conversation History.
- Test validace příloh a AI odpovědí.

3. Integrační testy
- PostgreSQL + pgvector v testovacím kontejneru.
- Alembic migrace.
- UNIQUE constraints, transakce a databázové lease.
- Test souběžných email jobs.
- Test API kontraktů pomocí FastAPI TestClient.

4. Bezpečnostní kontroly
- pip-audit – známé zranitelnosti Python závislostí.
- Bandit – základní bezpečnostní analýza Python kódu.
- Gitleaks – detekce secrets v repozitáři.
- Trivy – bezpečnostní kontrola Docker image.
- Kontrola, že image neobsahuje OAuth tokeny ani přístupové údaje.

5. Build
- Sestavení Docker image.
- Ověření instalace závislostí.
- Kontrola spuštění aplikace.
- Ověření kompatibility runtime a konfigurace.

6. Pravidla pro merge
- Všechny povinné CI kontroly musí úspěšně projít.
- Kritické bezpečnostní nálezy blokují merge.
- Breaking changes musí mít odpovídající testy.
- Změny databáze musí obsahovat Alembic migraci.
- Významné architektonické změny musí obsahovat ADR.
- Pro PoC jednoho vývojáře se používá self-review checklist.

7. Evidence
- Výsledek CI je uložen v GitHub Actions.
- Každý běh je navázán na commit nebo Pull Request.
- Neúspěšná kontrola musí být opravena před merge.

CÍL:
Automaticky zachytit chyby, bezpečnostní problémy a nekompatibilní změny před jejich začleněním do hlavní větve.

CI pipeline je zatím implementační návrh. Úspěšné běhy ani konkrétní výsledky testů nejsou dosud doložené.

### Jak proběhne release automaticky/ručně a kdo schvaluje produkci?

- ID: cd_pipeline (povinné)
- Stav: **PŘEDPOKLAD**

CONTINUOUS DELIVERY – REPLY MCFLY

Pro PoC použijeme automatizovaný build a kontrolované manuální schválení nasazení do GCP.

1. Spuštění release
- Po úspěšném CI a merge do hlavní větve lze spustit deployment workflow.
- Produkční nebo PoC deployment vyžaduje manuální schválení AI Engineerem.
- Release je navázán na konkrétní Git commit.

2. Build a publikování
- GitHub Actions sestaví Docker image.
- Image projde bezpečnostními kontrolami.
- Image se nahraje do Google Artifact Registry.
- Nasazení používá konkrétní image digest.

3. Autentizace do GCP
- GitHub Actions používá Workload Identity Federation.
- Nepoužíváme dlouhodobé JSON klíče servisních účtů.
- Deploy identita má pouze potřebná IAM oprávnění.

4. Databázové migrace
- Před nasazením se ověří kompatibilita databázového schématu.
- Alembic migrace se spouštějí jako samostatný řízený krok.
- Preferují se zpětně kompatibilní změny.
- Před rizikovou migrací se ověří možnost obnovení dat.

5. Cloud Run deployment
- Nasadí se nová revize Ingress.
- Nasadí se nová revize Workeru.
- Obě služby používají stejný Docker image.
- Konfigurace a servisní identity se nastavují podle prostředí.

6. Post-deployment ověření
- Kontrola dostupnosti Cloud Run služeb.
- Kontrola IAM/OIDC autentizace.
- Kontrola připojení k Cloud SQL.
- Kontrola Pub/Sub a Cloud Tasks.
- Test Gmail synchronizace.
- End-to-end test jedné automatické odpovědi.
- Kontrola správného Gmail vlákna a latence.

7. Rollback
- Při chybě lze vrátit provoz na předchozí kompatibilní Cloud Run revizi.
- Databázové migrace musí podporovat bezpečný návrat aplikace.
- Při nekonzistentním stavu se zpracování pozastaví a provede recovery.
- Nesmí vzniknout duplicitní automatické odpovědi.

8. Schvalování
- PoC release schvaluje AI Engineer / Solution Architect.
- Budoucí produkční release musí mít určeného provozního vlastníka.
- Automatický deployment do produkce bez schválení v první verzi nepoužíváme.

CÍL:
Reprodukovatelné nasazení s možností kontroly, testování a rollbacku bez zbytečně složité release infrastruktury.

### Jak eviduješ infrastrukturu a reprodukuješ ji?

- ID: infra_as_code (povinné)
- Stav: **PŘEDPOKLAD**

INFRASTRUCTURE AS CODE – REPLY MCFLY

Pro správu Google Cloud infrastruktury použijeme Terraform a jeden Git repozitář společně s aplikací.

1. Nástroj
- Terraform s Google Cloud providerem.
- Konkrétní verze Terraformu a provideru budou uzamčeny po ověření kompatibility.
- Infrastrukturou řízenou přes Terraform jsou opakovatelně vytvářené cloudové prostředky.

2. Struktura repozitáře

infra/
  terraform/
    main.tf
    variables.tf
    outputs.tf
    versions.tf

    modules/
      cloud_run/
      cloud_tasks/
      pubsub/
      cloud_sql/
      iam/
      scheduler/
      secrets/

    environments/
      poc/
        terraform.tfvars.example

3. Spravovaná infrastruktura
- Cloud Run Ingress a Worker.
- Pub/Sub topic a subscription.
- Cloud Tasks Sync Queue a Process Queue.
- Cloud SQL PostgreSQL.
- IAM servisní účty a oprávnění.
- Secret Manager prostředky bez ukládání tajných hodnot do Git.
- Cloud Scheduler.
- Potřebná GCP API a základní monitoring.

4. Terraform state
- Terraform state bude uložen ve vzdáleném GCS backendu.
- Bucket musí mít omezený IAM přístup a verzování objektů.
- State může obsahovat citlivé informace a nesmí být v Git repozitáři.
- Tajné hodnoty se nesmějí nekontrolovaně předávat přes Terraform state.

5. Review infrastruktury
- Změny probíhají prostřednictvím Pull Requestu.
- CI provádí terraform fmt a terraform validate.
- Terraform plan ukazuje plánované změny.
- Rizikové změny, zejména mazání databáze, vyžadují manuální kontrolu.

6. Deployment
- Po schválení se spustí terraform apply.
- Aplikace se následně nasadí do připravené infrastruktury.
- OAuth autorizace a citlivé hodnoty se konfigurují bezpečným odděleným postupem.

7. Drift detection
- Pravidelný terraform plan porovnává deklarovaný a skutečný stav.
- Nepředpokládané změny se vyhodnotí.
- Ruční změny v GCP Console se buď vrátí, nebo promítnou do Terraform konfigurace.
- Produkční změny nemají zůstávat pouze jako nezdokumentované ruční nastavení.

8. Reprodukovatelnost
- Nové prostředí lze vytvořit ze stejné Terraform konfigurace.
- Rozdíly jsou definované konfiguračními proměnnými.
- Zdrojový kód, Docker image a infrastruktura se verzují odděleně, ale v jednom repozitáři.

9. Ochrana kritických prostředků
- Cloud SQL musí mít definovanou zálohovací a obnovovací strategii.
- Použijeme ochranu proti nechtěnému smazání.
- Terraform destroy nesmí být součástí běžného CD workflow.

CÍL:
Udržovat infrastrukturu přehlednou, reprodukovatelnou a verzovanou bez manuálního vytváření každého cloudového prostředku.

Terraform je doporučená implementační volba. IaC konfigurace, vzdálený state a drift detection zatím nejsou vytvořeny ani otestovány.

### Jak oddělíš konfiguraci a tajemství pro jednotlivá prostředí?

- ID: env_secrets (povinné)
- Stav: **PŘEDPOKLAD**

KONFIGURACE A SECRETS – REPLY MCFLY

Použijeme oddělenou konfiguraci pro LOCAL a GCP PoC.

1. LOCAL – Docker Compose
- Konfigurace přes environment variables a lokální .env soubor.
- .env je v .gitignore a nikdy se necommituje.
- .env.example obsahuje pouze vzorové hodnoty.
- PostgreSQL běží lokálně v Docker kontejneru.
- Gmail a Gemini používají mock adaptéry nebo oddělená testovací credentials.
- Lokální credentials se nepřidávají do Docker image.

2. GCP PoC
- Běžná konfigurace přes Cloud Run environment variables.
- Gmail OAuth refresh token a další secrets v Google Secret Manageru.
- Cloud Run používá servisní identity a IAM.
- Přístup ke Google Cloud API prostřednictvím Application Default Credentials.
- Cloud SQL má samostatnou databázovou konfiguraci.

3. Oddělení prostředí
- Odlišné databáze a credentials.
- Odlišné konfigurační hodnoty a přístupová oprávnění.
- Pro GCP PoC se používá dedikovaná testovací Gmail schránka.
- Produkční credentials se nepoužívají při lokálních unit testech.

4. Bezpečnost
- Secrets nejsou v Git repozitáři.
- Secrets nejsou zabudované do Docker image.
- .gitignore a .dockerignore zabraňují nechtěnému přidání citlivých souborů.
- Secret Manager poskytuje verzování a řízení přístupu přes IAM.
- Při kompromitaci se credentials revokují a nahradí.

Cíl: Stejný aplikační kód běží lokálně i v GCP. Liší se pouze konfigurace a implementace externích adaptérů.

### Jak se vrátíš na předchozí verzi včetně změn DB?

- ID: rollback_plan (povinné)
- Stav: **PŘEDPOKLAD**

ROLLBACK STRATEGIE – REPLY MCFLY

1. Verzování aplikace
- Každý release má konkrétní Git commit a Docker image digest.
- Cloud Run uchovává předchozí revize aplikace.
- Ingress a Worker se nasazují ze stejného image.

2. Rollback Cloud Run
- Při chybě se pozastaví nebo omezí nové zpracování.
- Ověří se stav rozpracovaných úloh a outboxu.
- Provoz se vrátí na předchozí kompatibilní Cloud Run revizi.
- Následně se provedou smoke a integrační testy.

3. Databázové migrace
- PostgreSQL schéma se verzujeme pomocí Alembic.
- Preferujeme expand-contract migrace.
- Nové sloupce se přidávají před odstraněním původních.
- Starší a novější verze aplikace musí být během přechodu kompatibilní.

4. Rollback databáze
- Před rizikovou migrací vytvořit nebo ověřit zálohu Cloud SQL.
- Při chybě nejprve posoudit možnost opravy bez obnovy celé databáze.
- Destruktivní změny nevracet automaticky.
- Při obnově ze zálohy zkontrolovat ztracené změny od okamžiku zálohování.

5. Bezpečnost e-mailového zpracování
- Před obnovením práce ověřit email_jobs a email_outbox.
- Zprávy ve stavu SENT se nesmějí znovu odeslat.
- DELIVERY_UNKNOWN vyžaduje kontrolu Gmailu.
- Po obnovení PostgreSQL provést reconciliaci s Gmailem.

6. Ověření
- Test návratu na předchozí Cloud Run revizi.
- Test kompatibility databázového schématu.
- Test správného odeslání bez duplicit.
- Test obnovy přerušeného email job.

Cíl: Bezpečný návrat aplikace bez ztráty důležitých dat a bez duplicitních automatických odpovědí.

### Kdo spravuje doménu, DNS, TLS certifikáty a expirace?

- ID: domain_tls (doplňkové)
- Stav: **PŘEDPOKLAD**

DOMAIN, DNS A TLS – REPLY MCFLY

Pro počáteční PoC nepoužíváme vlastní webovou doménu.

1. Cloud Run
- Ingress a Worker používají standardní HTTPS adresy Cloud Run.
- TLS certifikáty pro tyto adresy spravuje Google Cloud.
- Není potřeba vlastní DNS zóna ani ruční obnova TLS certifikátů.

2. Autentizace endpointů
- Cloud Run vyžaduje IAM/OIDC autentizaci.
- Pub/Sub a Cloud Tasks komunikují prostřednictvím HTTPS.
- Anonymní přístup k aplikačním endpointům není povolen.

3. Gmail
- Systém používá dedikovanou Gmail schránku.
- E-mailovou doménu a infrastrukturu doručování spravuje poskytovatel Gmail.
- Aplikace neprovozuje vlastní SMTP server.

4. Odpovědnosti
- Google Cloud spravuje TLS pro standardní Cloud Run adresy.
- AI Engineer spravuje IAM, endpointy a jejich konfiguraci.
- Google spravuje infrastrukturu Gmail služby.

5. Budoucí rozšíření
- Vlastní doména není pro PoC potřebná.
- Pokud vznikne požadavek na vlastní doménu, doplníme DNS, certifikáty a monitoring expirace.

Cíl: Použít spravované HTTPS endpointy a eliminovat správu vlastní domény a TLS infrastruktury.

### Jak vypadají firewall pravidla, privátní síť a ingress?

- ID: network_design (doplňkové)
- Stav: **PŘEDPOKLAD**

NETWORK DESIGN – REPLY MCFLY

Pro PoC používáme jednoduchou síťovou architekturu Google Cloud s oddělením aplikačních endpointů a databáze.

1. Cloud Run Ingress
- Cloud Run ingress nastaven na internal.
- Přijímá Pub/Sub push požadavky ze stejného GCP projektu.
- Povinná IAM/OIDC autentizace.
- Přístup má pouze určená Pub/Sub servisní identita.
- Anonymní volání nejsou povolena.

2. Cloud Run Worker
- Cloud Run ingress nastaven na internal.
- Přijímá úlohy z Cloud Tasks ve stejném GCP projektu.
- Povinná IAM/OIDC autentizace.
- Přístup má pouze určená servisní identita Cloud Tasks.
- Samostatné veřejné uživatelské API neexistuje.

3. Cloud SQL PostgreSQL
- Databáze nebude mít veřejnou IP adresu.
- Použijeme privátní připojení z Cloud Run prostřednictvím podporované VPC konfigurace.
- Přístup bude omezen na oprávněné služby a databázové účty.
- Databáze nebude přístupná přímo z internetu.

4. Odchozí komunikace
- Worker potřebuje přístup k Gmail API, Vertex AI Gemini a dalším Google Cloud API.
- Odchozí přístup bude nakonfigurován tak, aby fungoval také při použití privátní databázové sítě.
- Nepovolujeme zbytečné příchozí spojení z veřejného internetu.

5. Firewall a zabezpečení
- Nevytváříme vlastní VM ani veřejné databázové porty.
- Přístup ke službám omezuje Cloud Run ingress, IAM a síťová konfigurace.
- Pro PoC nezavádíme Load Balancer, Cloud Armor ani vlastní WAF.
- Komunikace s externími API používá HTTPS/TLS.

6. Testování
- Neautorizované požadavky musí být odmítnuty.
- Pub/Sub musí úspěšně doručit notifikaci.
- Cloud Tasks musí úspěšně spustit Worker.
- Worker musí přistupovat k privátnímu PostgreSQL.
- Worker musí mít funkční odchozí připojení ke Gmail a Vertex AI API.

Cíl: Minimalizovat veřejně dostupné služby a zachovat jednoduchou, zabezpečenou infrastrukturu vhodnou pro cloudové PoC.

### Kde ukládáš buildy a jak verifikuješ jejich původ?

- ID: artifacts_registry (doplňkové)
- Stav: **PŘEDPOKLAD**

ARTIFACT REGISTRY – REPLY MCFLY

Pro ukládání Docker image použijeme Google Artifact Registry.

1. Úložiště
- Jeden privátní Docker repository v GCP.
- Název: reply-mcfly.
- Výchozí region: europe-west1.
- Obsahuje verzované Docker image aplikace.

2. Build
- Docker image vzniká z verzovaného Git commitu.
- Jeden image se používá pro Cloud Run Ingress a Worker.
- Image obsahuje Python/FastAPI aplikaci a potřebné knihovny.
- Credentials a soukromé soubory nejsou součástí image.

3. Verzování
- Každý image má identifikátor verze nebo Git commit SHA.
- Deployment používá jednoznačný image digest (SHA-256).
- Nepoužíváme latest jako identifikátor produkčního release.
- Git commit, Docker image a Cloud Run revize musí být dohledatelné.

4. Bezpečnost
- Přístup k Artifact Registry omezuje Google IAM.
- Pouze autorizovaná build identita může publikovat image.
- Cloud Run má pouze potřebné oprávnění ke čtení image.
- Docker image prochází bezpečnostním skenováním pomocí Trivy nebo Artifact Analysis.

5. Ověření původu
- Build je navázán na konkrétní Git commit a CI run.
- Při deploymentu se kontroluje image digest.
- CI musí úspěšně dokončit testy a bezpečnostní kontroly.
- Později lze doplnit kryptografické podepisování a ověřování build provenance.

6. Retence
- Uchováváme aktuální image a několik předchozích release verzí pro rollback.
- Staré nepoužívané image lze odstranit podle retenčních pravidel.
- Image aktivně používaný Cloud Run revizí se nesmí nekontrolovaně odstranit.

Cíl: Reprodukovatelný deployment, dohledatelný původ aplikace a bezpečný rollback pomocí konkrétních verzí Docker image.

### Jaké jsou pravidla branchí, tagů a verzování?

- ID: branching_release (doplňkové)
- Stav: **PŘEDPOKLAD**

GIT BRANCHING A RELEASE STRATEGY – REPLY MCFLY

Pro PoC používáme jednoduchou GitHub Flow strategii.

1. Hlavní větev
- main – stabilní hlavní větev projektu.
- Přímé změny do main nejsou doporučené.
- Každá funkční změna probíhá v samostatné pracovní větvi.

2. Pracovní větve
- feature/ – nové funkce.
- fix/ – opravy chyb.
- docs/ – změny dokumentace.
- infra/ – změny GCP infrastruktury.

Příklady:
- feature/gmail-sync
- feature/thread-awareness
- feature/rag
- feature/web-search
- fix/duplicate-reply
- infra/cloud-run-deployment

3. Pull Request
- Každá významná změna se začlení přes Pull Request.
- CI provede lint, typovou kontrolu, testy a bezpečnostní skenování.
- Změny databáze musí obsahovat odpovídající Alembic migrace.
- Architektonické změny se zaznamenají pomocí ADR.
- V rámci PoC jednoho vývojáře se používá self-review.

4. Verzování
- Použijeme Semantic Versioning: MAJOR.MINOR.PATCH.
- MAJOR – nekompatibilní změna.
- MINOR – nová zpětně kompatibilní funkcionalita.
- PATCH – oprava bez změny hlavního kontraktu.

5. Release tagy
- v0.1.0 – první funkční Gmail end-to-end workflow.
- v0.2.0 – Conversation History.
- v0.3.0 – RAG.
- v0.4.0 – Live Web Search.
- v1.0.0 – dokončené a otestované PoC se všemi požadovanými funkcemi.

Uvedené verze jsou plánované milníky, nikoliv již vydané release.

6. Docker image
- Každý release je navázán na Git tag a commit SHA.
- Image se ukládá do Google Artifact Registry.
- Cloud Run používá konkrétní image digest.

7. CHANGELOG
- Změny se zapisují do CHANGELOG.md.
- Evidují se nové schopnosti, opravy, bezpečnostní změny a breaking changes.

8. Hotfix a rollback
- Kritická oprava vzniká v samostatné fix větvi.
- Po úspěšných testech se začlení do main.
- Při chybném deploymentu lze vrátit předchozí kompatibilní Cloud Run revizi.

Cíl: Jednoduché verzování, dohledatelnost změn a reprodukovatelný deployment bez složitého Git branching modelu.

### Jak se provádějí schema migrace před/po deploy?

- ID: database_deploy (doplňkové)
- Stav: **PŘEDPOKLAD**

DATABASE DEPLOYMENT A MIGRACE – REPLY MCFLY

Pro správu databázového schématu používáme Alembic, SQLAlchemy 2.x a PostgreSQL.

1. Verzování schématu
- Každá změna databáze má vlastní Alembic migraci.
- Migrační soubory jsou součástí Git repozitáře v adresáři migrations/.
- Databáze eviduje aktuální verzi pomocí alembic_version.
- Migrace jsou součástí stejného release jako aplikační kód.

2. Lokální vývoj
- PostgreSQL + pgvector běží v Docker Compose.
- Vývojář spustí databázové migrace příkazem alembic upgrade head.
- Migrace se testují před nasazením do GCP.
- Ověřují se tabulky, constraints, indexy a referenční integrita.

3. Před deploymentem do GCP
- Ověřit úspěšné CI testy.
- Ověřit kompatibilitu nové a předchozí verze aplikace.
- Zkontrolovat možnost obnovy databáze.
- Spustit kompatibilní Alembic migrace jako samostatný řízený krok, například přes Cloud Run Job.
- Ověřit úspěšné dokončení migrace.

4. Deployment aplikace
- Nasadit nový Docker image do Cloud Run.
- Ingress a Worker používají stejnou verzi aplikačního kódu.
- Nová aplikace musí být kompatibilní s aktuálním databázovým schématem.

5. Po deploymentu
- Ověřit databázové připojení.
- Ověřit verzi schématu.
- Spustit smoke a integrační testy.
- Ověřit Gmail synchronizaci, email_jobs a email_outbox.
- Zkontrolovat správné odeslání testovací odpovědi.

6. Rollback
- Preferovat zpětně kompatibilní migrace (expand-contract).
- Při chybě aplikace vrátit předchozí kompatibilní Cloud Run revizi.
- Destruktivní databázové změny nevracet automaticky.
- Při nutnosti obnovy použít ověřenou zálohu Cloud SQL a provést reconciliaci s Gmailem.

7. Bezpečnost
- Migrace spouští pouze autorizovaná servisní identita.
- Worker nespouští migrace automaticky při každém startu.
- Migrace se nesmějí souběžně spouštět z více instancí.

Cíl: Bezpečné a reprodukovatelné změny databáze bez ztráty stavu zpracování nebo duplicitních e-mailových odpovědí.

### Budeš používat preview prostředí pro PR a anonymizovaná data?

- ID: preview_env (doplňkové)
- Stav: **PŘEDPOKLAD**

PREVIEW ENVIRONMENT – REPLY MCFLY

Pro první PoC nebudeme vytvářet samostatné cloudové preview prostředí pro každý Pull Request.

Důvody:
- Projekt vyvíjí jeden AI Engineer.
- Používáme omezený GCP trial/free-tier rozpočet.
- Každé další prostředí by mohlo vytvářet dodatečné náklady na Cloud SQL a další služby.
- Pro ověření změn postačuje lokální Docker Compose a jedno GCP PoC prostředí.

1. Lokální testování
- Docker Compose spouští Ingress, Worker a PostgreSQL/pgvector.
- Externí integrace lze nahradit mockovanými adaptéry.
- Unit a integrační testy používají syntetická data.
- Každý Pull Request musí projít CI kontrolami.

2. GCP PoC
- Jedno izolované cloudové prostředí.
- Dedikovaná testovací Gmail schránka.
- Skutečné Gmail API, Cloud Tasks, Pub/Sub, Cloud Run a Gemini.
- Používají se syntetické e-maily, přílohy a fiktivní RAG dokumenty.
- Slouží pro integrační, end-to-end a demonstrační testy.

3. Testovací data
- Nepoužívat kopie skutečných soukromých e-mailů.
- Testovací dokumenty a přílohy musí být syntetické.
- Pokud by byla potřebná reálná data, jejich použití vyžaduje samostatné schválení a odpovídající ochranu.
- Pouhá pseudonymizace není totéž co anonymizace.

4. Budoucí rozšíření
- Při rozšíření týmu lze zavést dočasná preview prostředí pro Pull Requesty.
- Prostředí budou vytvářena automatizovaně pomocí Infrastructure as Code.
- Budou používat oddělené credentials a testovací databázi.
- Po ukončení testování se automaticky odstraní.

Cíl: Zachovat jednoduchý vývojový proces, nízké náklady a bezpečné testování bez nepotřebných cloudových prostředí.

### Jaké máš budget alerty, limity a odhad ceny prostředí?

- ID: infra_cost_controls (doplňkové)
- Stav: **PŘEDPOKLAD**

INFRASTRUCTURE COST CONTROLS – REPLY MCFLY

Cílem je provozovat PoC v rámci dostupného Google Cloud trial kreditu a zabránit nekontrolovanému růstu nákladů.

1. Rozpočet a upozornění
- Pro PoC navrhujeme počáteční měsíční rozpočet 20 USD.
- Google Cloud Billing Budget nastavíme s upozorněními na 50 %, 80 % a 100 % rozpočtu.
- Rozpočtové výstrahy jsou upozornění, nikoliv automatické zastavení účtování.
- Skutečný rozpočet bude potvrzen po nacenění všech služeb.

2. Cloud Run
- Ingress: max. 2 instance, concurrency 10.
- Worker: max. 3 instance, concurrency 1.
- Min instances: 0.
- CPU a paměť zvolíme podle naměřených požadavků.
- Škálování na nulu omezuje náklady při nečinnosti.

3. Cloud Tasks
- Sync Queue: maximálně 1 současná synchronizace.
- Process Queue: maximálně 3 současné úlohy.
- Dispatch rate omezíme podle kapacity a API kvót.
- Retry bude mít omezený počet pokusů.

4. Cloud SQL PostgreSQL
- Pro PoC použijeme nejmenší vhodnou konfiguraci podporující PostgreSQL a pgvector.
- Databáze představuje průběžný náklad i bez aktivních požadavků.
- Budeme sledovat velikost úložiště, CPU, počet spojení a náklady na zálohy.
- Konfigurace musí být ověřena podle dostupného trial rozpočtu.

5. Vertex AI Gemini
- Zvolíme cenově efektivní multimodální model.
- Omezíme délku historie vlákna a velikost kontextu.
- Nastavíme maximální počet výstupních tokenů.
- Omezíme počet opakovaných inference.
- Budeme evidovat spotřebu tokenů na email job.

6. RAG a Web Search
- RAG používá pouze 1–3 fiktivní dokumenty.
- Embeddingy dokumentů generujeme při importu nebo změně.
- RAG retrieval spouštíme pouze při relevantním dotazu.
- Web Search používáme pouze při potřebě aktuálních informací.
- Vyhneme se zbytečným externím voláním.

7. Další cloudové služby
- Pub/Sub, Cloud Tasks, Scheduler a Secret Manager používáme pouze v potřebném rozsahu.
- Cloud Logging nebude ukládat obsahy e-mailů ani příloh.
- Omezíme množství a dobu uchovávání provozních logů.
- Staré nepoužívané Docker image odstraníme podle retenčních pravidel.

8. Měření
- Celkové měsíční náklady GCP.
- Náklady na jeden zpracovaný e-mail.
- Gemini tokeny na email job.
- Náklady Cloud SQL a Cloud Run.
- Počet Web Search volání.
- Počet retry a neúspěšných úloh.

9. Odhad ceny
- Přesná cena prostředí zatím není stanovena.
- Dominantními položkami budou pravděpodobně Cloud SQL a Vertex AI Gemini.
- Odhad vypočítáme pomocí Google Cloud Pricing Calculator a aktuálních ceníků.
- Výslednou cenu ověříme skutečným provozem PoC.

DŮLEŽITÉ:
Rozpočet 20 USD je návrhový limit pro sledování nákladů, nikoliv potvrzená cena provozu. Nemusí pokrýt náklady všech požadovaných služeb.

Cíl: Zajistit kontrolovatelné náklady bez omezení povinných funkcí Conversation History, RAG a Live Web Search.

## 12 · Testovací strategie a Definition of Done

*Cíl:* Každé kritické tvrzení musí mít důkaz, nejen zaškrtávátko.

*Gate:* AC a NFR jsou svázané s testy a nejdůležitější výpadky jsou prověřené.

### Jak rozdělíš unit, integration, contract, E2E a manuální testy?

- ID: test_strategy (povinné)
- Stav: **PŘEDPOKLAD**

TEST STRATEGY – REPLY MCFLY

Použijeme pytest a kombinaci automatizovaných testů s omezeným počtem manuálních E2E testů.

1. Unit Tests
- Testování jednotlivých Python modulů bez skutečných cloudových služeb.
- Mockované Gmail, Gemini, RAG, Web Search a Cloud Tasks adaptéry.
- Ověření stavového automatu, deduplikace, validace příloh a bezpečnostních pravidel.
- Test Conversation History, výběru kontextu a AI orchestrace.

2. Integration Tests
- Lokální PostgreSQL/pgvector v Docker Compose.
- Ověření Alembic migrací, SQL transakcí, UNIQUE constraints a lease.
- Test komunikace FastAPI s databází.
- Samostatné integrační testy skutečného Gmail API a Vertex AI Gemini v GCP PoC.

3. Contract Tests
- Validace FastAPI request/response schémat pomocí Pydantic.
- Test kompatibility Cloud Tasks payloadů.
- Test rozhraní GmailPort, LLMPort, KnowledgeRepository a WorkflowRunner.
- Simulace neplatných odpovědí a změn externích API.

4. End-to-End Tests
- Skutečný Gmail → Pub/Sub → Cloud Tasks → Cloud Run → Gemini → Gmail Reply.
- Ověření správného Gmail vlákna a příjemce.
- Test všech pěti podporovaných příloh.
- Samostatné testy Conversation History, RAG a Web Search.
- Kombinovaný test všech tří pokročilých funkcí.
- Měření doby od přijetí e-mailu do odeslání odpovědi pod 120 sekund.

5. Security Tests
- Neplatná OIDC autentizace.
- Prompt injection v e-mailu a přílohách.
- Neplatné a nadlimitní soubory.
- Neoprávněná změna příjemce.
- Únik citlivých údajů do logů.

6. Manual Tests
- Kontrola odpovědi v Gmailu.
- Ověření čitelnosti a správnosti odpovědi.
- Kontrola zdrojů RAG a Web Search.
- Kontrola provozních logů a metrik v GCP.

7. Automatizace
- Unit, contract a lokální integration testy běží v CI.
- Cloudové E2E testy se spouštějí před vydáním PoC.
- Výsledky jsou evidovány podle Git commitu a testovacího scénáře.

Cíl: Testovat každou komponentu izolovaně i celý systém jako funkční celek.

### Které 3 klíčové cesty bude chránit automatický E2E test?

- ID: critical_e2e (povinné)
- Stav: **PŘEDPOKLAD**

CRITICAL END-TO-END SCENARIOS – REPLY MCFLY

E2E-01 – Automatické zpracování e-mailu s přílohou

Vstup:
- Nový nepřečtený e-mail v dedikované Gmail schránce.
- Podporovaná příloha PDF, MP3, WAV, JPEG nebo PNG.

Očekávaný výsledek:
- Gmail Watch spustí automatické zpracování.
- Worker správně interpretuje obsah zprávy a přílohy.
- Gemini vytvoří relevantní odpověď.
- Gmail odešle odpověď do původního vlákna.
- Nevznikne duplicitní odpověď.
- Celková latence je pod 120 sekund.

E2E-02 – Conversation History a izolace vláken

Vstup:
- Více navazujících e-mailů ve stejném Gmail vlákně.
- Samostatné nesouvisející vlákno.

Očekávaný výsledek:
- Asistent správně využije předchozí zprávy aktuálního vlákna.
- Nepoužije informace z jiného vlákna.
- Odpověď zachová správný threadId a e-mailové hlavičky.
- Nevznikne duplicitní odpověď.
- Latence je pod 120 sekund.

E2E-03 – RAG + Live Web Search

Vstup:
- E-mail obsahující dotaz na fiktivní produkt a aktuální veřejnou informaci.

Očekávaný výsledek:
- RAG získá správná fakta ze schváleného znalostního dokumentu.
- Web Search ověří aktuální informaci z veřejných zdrojů.
- Gemini vytvoří odpověď založenou na obou zdrojích.
- Odpověď rozlišuje interní znalosti a veřejné zdroje.
- Neuvádí nepodložená fakta.
- Soukromý obsah e-mailu není předán do veřejného vyhledávání.
- Odpověď je odeslána do původního vlákna do 120 sekund.

DOPLŇKOVÉ TESTY:
- Každý formát přílohy samostatně.
- RAG a Web Search samostatně.
- Kombinace Conversation History + RAG + Web Search.
- Duplicitní Pub/Sub/Cloud Tasks událost.
- Timeout Gmail API a Gemini.
- Výpadek databáze.
- Restart Workeru.
- DELIVERY_UNKNOWN.

Tři hlavní E2E scénáře chrání základní funkčnost a všechny pokročilé schopnosti. Doplňkové testy pokrývají jednotlivé formáty, chybové stavy a kombinace funkcí.

### Jak připravíš stabilní testovací data bez produkčních osobních údajů?

- ID: test_data (povinné)
- Stav: **PŘEDPOKLAD**

TEST DATA MANAGEMENT – REPLY MCFLY

Použijeme syntetická a verzovaná testovací data. Nebudeme kopírovat produkční e-maily ani soukromé přílohy.

1. Testovací e-maily
- Předem připravené MIME zprávy.
- Jednoduchý textový dotaz.
- Navazující konverzace s více zprávami.
- Dvě nezávislá Gmail vlákna.
- Duplicitní a automaticky generované zprávy.
- Neplatné MIME a chybné hlavičky.

2. Testovací přílohy
- PDF – syntetický dokument s ověřitelnými informacemi.
- MP3 – krátká testovací nahrávka.
- WAV – krátká testovací nahrávka.
- JPEG – obrázek s jednoznačným testovacím obsahem.
- PNG – obrázek s jednoznačným testovacím obsahem.
- Neplatné a nadlimitní soubory.

3. RAG dokumenty
- 1–3 fiktivní znalostní dokumenty.
- Každý dokument má verzi, checksum a očekávané odpovědi.
- Testy ověřují, že retrieval skutečně mění výstup AI.
- Testují se také informace, které v dokumentech nejsou.

4. Web Search
- Pro unit testy používat předem definované veřejné výsledky.
- Testovat správné zdroje, zastaralé informace a prázdné výsledky.
- Skutečný Live Web Search ověřovat odděleně v GCP.
- Testovací dotazy nesmějí obsahovat soukromá data.

5. Databáze
- Testovací PostgreSQL/pgvector.
- Migrace spouštěné před integračními testy.
- Každý test používá izolovaný stav.
- Testovací data se po skončení obnoví nebo odstraní.

6. Reprodukovatelnost
- Bezpečné fixtures jsou verzované v Git repozitáři.
- Náhodně generovaná data používají pevný seed.
- Očekávané výsledky jsou definované před spuštěním testů.
- Externí AI výstupy se v unit testech mockují kvůli determinismu.

7. Bezpečnost
- Žádné skutečné OAuth tokeny ani credentials.
- Žádné skutečné soukromé e-maily.
- Žádná produkční databázová záloha.
- Testovací Gmail schránka je oddělená od osobních účtů.

Cíl: Stabilní, opakovatelné a bezpečné testování bez práce s produkčními osobními údaji.

Mám testovací data připravená ve složce -> musíš se na ně doptat

### Co musí projít před merge a před release?

- ID: quality_gates (povinné)
- Stav: **PŘEDPOKLAD**

QUALITY GATES – REPLY MCFLY

1. Před merge do main
- Ruff lint a format check.
- Pyright nebo mypy type check.
- pytest unit tests.
- PostgreSQL integration tests.
- FastAPI contract tests.
- Kontrola Alembic migrací.
- pip-audit pro Python závislosti.
- Gitleaks pro secrets.
- Trivy nebo Artifact Analysis pro Docker image.
- Úspěšné sestavení Docker image.

2. Bezpečnostní požadavky
- Žádné neřešené kritické zranitelnosti.
- Žádné secrets v repozitáři.
- Žádné neautorizované změny IAM.
- Žádné známé chyby umožňující duplicitní odeslání.
- Žádné porušení izolace Gmail vláken.

3. Před release do GCP PoC
- Úspěšný CI pipeline.
- Úspěšné databázové migrace.
- Kontrola konfigurace Cloud Run, Cloud Tasks a Pub/Sub.
- Ověření Gmail OAuth a Vertex AI přístupu.
- Automatické E2E testy hlavních scénářů.
- Ověření všech pěti formátů příloh.
- Ověření Conversation History, RAG a Web Search.
- Test kombinace všech tří pokročilých funkcí.
- Test duplicity, retry a chyb externích API.
- Ověření latence pod 120 sekund v definovaných testovacích scénářích.

4. Release approval
- Všechny povinné testy musí projít.
- Kritické chyby blokují release.
- Otevřené nekritické nálezy musí být zdokumentované.
- AI Engineer / Solution Architect schvaluje release PoC.

5. Evidence
- CI výsledky navázané na commit.
- E2E test reporty.
- Bezpečnostní test report.
- Metriky latence z Cloud Monitoring.
- Identifikátor nasazeného Docker image.

Cíl: Žádný release nesmí být označen za úspěšný bez doloženého výsledku požadovaných testů.

### Kdo provede a schválí UAT s konkrétními AC?

- ID: uat_owner (povinné)
- Stav: **PŘEDPOKLAD**

USER ACCEPTANCE TESTING – REPLY MCFLY

UAT pro PoC provádí AI Engineer / Solution Architect podle předem definovaných akceptačních kritérií.

1. Odpovědnost
- Příprava UAT scénářů: AI Engineer.
- Provedení testů: AI Engineer.
- Technické schválení PoC: AI Engineer / Solution Architect.
- Externí potvrzení výsledků, pokud je vyžadováno, provádí příslušný hodnotitel nebo vlastník řešení.

2. Akceptační kritéria

AC-01:
Nový nepřečtený e-mail automaticky spustí zpracování bez manuálního zásahu.

AC-02:
Systém správně zpracuje PDF, MP3, WAV, JPEG a PNG přílohy.

AC-03:
Conversation History používá relevantní předchozí zprávy stejného vlákna.

AC-04:
Kontext nesouvisejících Gmail vláken zůstává izolovaný.

AC-05:
RAG poskytuje odpovědi na základě 1–3 fiktivních znalostních dokumentů.

AC-06:
Systém nevymýšlí produktová fakta, která nejsou dostupná ve znalostní bázi.

AC-07:
Live Web Search získává aktuální veřejné informace z relevantních zdrojů.

AC-08:
Conversation History, RAG a Web Search fungují samostatně i společně.

AC-09:
Odpověď je odeslána do původního Gmail vlákna se správnými hlavičkami.

AC-10:
Duplicitní událost nezpůsobí další automatickou odpověď.

AC-11:
Systém bezpečně reaguje na neplatné přílohy a dočasné chyby externích API.

AC-12:
End-to-end zpracování splní limit pod 120 sekund v definovaných testovacích scénářích.

3. Evidence
- Test case ID.
- Vstupní testovací e-mail.
- Očekávaný výsledek.
- Skutečný výsledek.
- PASS/FAIL.
- Naměřená latence.
- Job ID a odkaz na relevantní logy.
- Identifikátor testované verze aplikace.

4. Schválení
- PoC může být technicky schváleno pouze při splnění povinných akceptačních kritérií.
- Nesplněné požadavky musí být zdokumentované.
- Výsledek UAT je součástí finální demonstrační dokumentace.

### Jak otestuješ timeout, výpadek DB, chybné API a retry?

- ID: failure_tests (povinné)
- Stav: **PŘEDPOKLAD**

FAILURE AND RECOVERY TESTING – REPLY MCFLY

Testy simulují selhání externích služeb a ověřují bezpečné obnovení zpracování.

1. Timeout Gemini
- Mock Gemini Adapteru vyvolá timeout.
- Worker nesmí překročit aplikační deadline.
- Úloha přejde do odpovídajícího chybového stavu.
- Retry proběhne pouze při dostatečném časovém rozpočtu.
- Nesmí být odeslána nepodložená odpověď.

2. Výpadek PostgreSQL
- Během zpracování simulovat nedostupnou databázi.
- Worker nesmí pokračovat bez bezpečné evidence stavu.
- Cloud Tasks provede opakování podle retry politiky.
- Po obnově databáze se úloha bezpečně obnoví.
- Nevznikne duplicitní odpověď.

3. Gmail API chyba
- Simulovat HTTP 429, 500 a 503.
- Ověřit exponential backoff.
- Ověřit správnou klasifikaci retryable a non-retryable chyb.
- Ověřit, že Gmail Send se při nejasném výsledku slepě neopakuje.

4. DELIVERY_UNKNOWN
- Simulovat úspěšné Gmail Send bez doručeného potvrzení.
- Worker uloží DELIVERY_UNKNOWN.
- Recovery ověří stav v Gmailu.
- Druhá odpověď se neodešle, pokud původní již existuje.

5. Restart Workeru
- Ukončit Worker během PROCESSING.
- Ověřit persistentní stav v PostgreSQL.
- Po expiraci lease povolit bezpečné převzetí úlohy.
- Zastaralý Worker nesmí přepsat stav nového vlastníka.

6. Duplicitní události
- Doručit stejnou Pub/Sub notifikaci opakovaně.
- Vytvořit více Cloud Tasks požadavků na stejný job.
- Ověřit UNIQUE(mailbox_id, gmail_message_id).
- Ověřit maximálně jednu odpověď.

7. Výpadek Web Search
- Simulovat nedostupné vyhledávání.
- Asistent nesmí prezentovat neověřené aktuální informace jako fakta.
- Použije bezpečnou chybovou odpověď nebo NEEDS_REVIEW.

8. Výpadek RAG
- Simulovat neúspěšný retrieval.
- Pokud jsou interní fakta nezbytná, model je nesmí vymýšlet.
- Úloha přejde do definovaného stavu nebo vytvoří bezpečnou odpověď.

9. Překročení 120 sekund
- Simulovat dlouhé čekání ve frontě nebo pomalé API.
- Změřit skutečnou end-to-end latenci.
- Ověřit správné přerušení dalšího zpracování.
- Zaznamenat překročení jako nesplněný výkonnostní test.

10. Ověření
- Každý test má očekávaný stav a PASS/FAIL.
- Eviduje se job_id, chybový kód a latence.
- Automatizované testy běží v pytest.
- Klíčové scénáře se ověří také v GCP PoC.

Cíl: Prokázat, že systém bezpečně selhává, neodesílá duplicitní zprávy a dokáže obnovit zpracování po dočasných chybách.

### Kdy proběhnou security scanning/review/penetration testy?

- ID: security_tests (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jakým nástrojem a workloadem ověříš p95 a kapacitu?

- ID: performance_tests (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak otestuješ přístupnost?

- ID: accessibility_tests (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jaké prohlížeče/verze OS/zařízení podporuješ?

- ID: compatibility_tests (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kdo udržuje flaky testy a testovací prostředí?

- ID: test_ownership (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kde jsou výsledky testů, screenshoty, logy a reporty?

- ID: evidence_links (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak prokážeš FR-XX -> AC-XX -> TEST-XX -> build?

- ID: test_traceability (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Který regression suite musí běžet před hotfixem?

- ID: regression_plan (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

## 13 · Observability, provoz a obnova

*Cíl:* V produkci víš, co se děje, a umíš zasáhnout.

*Gate:* Každý důležitý user journey má metriku, alert a vlastníka.

### Jaké metriky pro uživatele a business flow měříš?

- ID: monitoring_scope (povinné)
- Stav: **PŘEDPOKLAD**

MONITORING SCOPE – REPLY MCFLY

Použijeme Google Cloud Monitoring, Cloud Logging a strukturované aplikační metriky.

1. Hlavní uživatelská metrika
- End-to-end latency: čas od přijetí e-mailu do Gmail schránky po potvrzené odeslání odpovědi.
- Cílový limit: pod 120 sekund.
- Sledujeme p50, p95, maximum a počet překročení limitu.
- Rozlišujeme čas běžného úspěšného zpracování od neúspěšných úloh.

2. Business flow metriky
- Počet detekovaných nových nepřečtených zpráv.
- Počet zařazených email jobs.
- Počet úspěšně odeslaných odpovědí (SENT).
- Počet selhání (FAILED).
- Počet úloh vyžadujících kontrolu (NEEDS_REVIEW).
- Počet nejasných odeslání (DELIVERY_UNKNOWN).
- Počet bezpečně přeskočených zpráv (SKIPPED).
- Počet detekovaných duplicit.

3. Latence jednotlivých komponent
- Gmail Watch / Pub/Sub notification delay.
- Cloud Tasks queue waiting time.
- Gmail synchronizace.
- Načítání zpráv a příloh.
- Conversation History retrieval.
- RAG retrieval.
- Web Search.
- Gemini inference.
- Validace a Gmail Send.

4. Infrastrukturní metriky
- Cloud Run instance count, concurrency, CPU a paměť.
- Počet čekajících Cloud Tasks úloh a stáří nejstarší úlohy.
- Cloud SQL CPU, počet připojení a latence dotazů.
- Chybovost externích API.
- Počet retry a HTTP 429/5xx.

5. AI metriky
- Počet Gemini volání na e-mail.
- Spotřeba vstupních a výstupních tokenů.
- Počet použití Conversation History, RAG a Web Search.
- Počet neplatných AI výstupů.
- Úspěšnost retrieval na testovacích dotazech.
- Odhad nákladů na jeden zpracovaný e-mail.

6. Spolehlivost
- Úspěšnost zpracování zpráv.
- Počet duplicitně odeslaných odpovědí (cílová hodnota 0).
- Počet ztracených zpráv (cílová hodnota 0).
- Počet úloh obnovených po selhání.

Všechny metriky se vyhodnocují v definovaném časovém období. Systém neprohlašujeme za vyhovující 120sekundovému limitu bez doložených end-to-end měření.

### Jaké logy, traces a correlation IDs zavedeš bez úniku dat?

- ID: logs_traces (povinné)
- Stav: **PŘEDPOKLAD**

LOGGING, TRACING A CORRELATION – REPLY MCFLY

Použijeme strukturované JSON logování přes Python logging a Google Cloud Logging.

1. Identifikátory
- correlation_id – identifikátor průchodu jedné události systémem.
- job_id – interní UUID úlohy.
- trace_id – identifikátor distribuované trace, pokud je dostupný.
- task_name – identifikátor Cloud Tasks úlohy.
- component – název aplikační komponenty.

2. Klíčové události
- gmail_notification_received.
- gmail_sync_started / completed / failed.
- email_job_created.
- email_processing_started.
- attachment_validation_completed.
- thread_context_loaded.
- rag_retrieval_completed.
- web_search_completed.
- gemini_inference_completed.
- reply_ready.
- gmail_send_completed.
- email_processing_failed.
- delivery_unknown.
- duplicate_skipped.
- recovery_started / completed.

3. Struktura logu
- timestamp.
- severity.
- component.
- event_type.
- correlation_id.
- job_id.
- status.
- duration_ms.
- error_code.
- retry_count.

4. Distributed tracing
- Měřit jednotlivé fáze zpracování e-mailu.
- Propagovat correlation_id mezi Ingress, Cloud Tasks a Workerem.
- Pro pokročilé trasování lze použít OpenTelemetry a Cloud Trace.
- Pro počáteční PoC postačí strukturované logy s identifikátory a měřením trvání jednotlivých operací.

5. Ochrana dat
- Nelogovat těla e-mailů ani obsah příloh.
- Nelogovat celé AI prompty a odpovědi.
- Nelogovat OAuth tokeny, secrets ani Authorization hlavičky.
- E-mailové adresy a externí identifikátory minimalizovat nebo pseudonymizovat.
- Logy nesmějí obsahovat kompletní Pub/Sub ani Cloud Tasks payloady s citlivým obsahem.

6. Retence a přístup
- Přístup k logům řídit pomocí IAM.
- Nastavit přiměřenou retenční dobu.
- Pro PoC navrhujeme 30denní aplikační retenci, podle možností konkrétní logovací konfigurace.
- Cloud Audit Logs mají vlastní pravidla uchovávání.

7. Ověření
- Dohledat konkrétní email job podle job_id.
- Ověřit návaznost Ingress → Sync → Process → Gmail Send.
- Zkontrolovat logy na přítomnost citlivých informací.
- Změřit trvání jednotlivých kroků.

Cíl: Zajistit úplnou technickou dohledatelnost zpracování bez ukládání soukromého e-mailového obsahu do logů.

### Jaké alerty se spouštějí, při jaké hranici a komu?

- ID: alerts (povinné)
- Stav: **PŘEDPOKLAD**

ALERTING STRATEGY – REPLY MCFLY

Použijeme Google Cloud Monitoring a upozornění na e-mail správce projektu. Pro kritické selhání samotné Gmail integrace musí být notifikace doručována nezávislým kanálem.

1. End-to-end latency
- WARNING: p95 přesáhne 90 sekund v 10minutovém okně při dostatečném počtu vzorků.
- CRITICAL: jakýkoliv potvrzený email job překročí 120 sekund.
- Při nízkém objemu testů vyhodnocujeme jednotlivé úlohy, nikoliv pouze percentily.

2. Chybovost zpracování
- WARNING: alespoň 3 neúspěšné úlohy během 10 minut.
- CRITICAL: opakovaná selhání základního Gmail workflow nebo nemožnost odesílat odpovědi.

3. Cloud Tasks
- WARNING: nejstarší čekající úloha přesáhne 30 sekund.
- CRITICAL: nejstarší čekající úloha přesáhne 60 sekund.
- Sledujeme také počet neúspěšných dispatch pokusů.

4. Gmail API / Gemini
- WARNING: opakované HTTP 429 nebo 5xx.
- CRITICAL: opakované selhání nezbytné integrace a nemožnost dokončit email job.

5. PostgreSQL
- WARNING: CPU přesáhne 80 % po dobu 5 minut.
- WARNING: využití databázových spojení přesáhne 80 % dostupného limitu.
- CRITICAL: databáze není dostupná pro Worker.

6. Bezpečnost a idempotence
- CRITICAL: potvrzené duplicitní odeslání odpovědi.
- CRITICAL: potvrzený neoprávněný přístup nebo únik citlivých dat.
- WARNING: zvýšený počet neautorizovaných požadavků.

7. Gmail Watch
- WARNING: blížící se expirace Watch bez úspěšného obnovení.
- CRITICAL: Watch expiroval a recovery synchronizace selhává.

8. Náklady
- Google Cloud Billing Budget: upozornění při 50 %, 80 % a 100 % nastaveného rozpočtu.
- Rozpočtové upozornění samo o sobě nezastavuje účtování.

9. Příjemce
- AI Engineer / Solution Architect.
- V případě budoucí produkce určený provozní vlastník.

Hranice jsou výchozí návrhové hodnoty. Po zátěžových testech je upravíme podle skutečného provozu a počtu zpráv.

### Kdo řeší výpadky, v jakých hodinách a jak ho kontaktovat?

- ID: on_call (povinné)
- Stav: **PŘEDPOKLAD**

ON-CALL A PROVOZNÍ ODPOVĚDNOST – REPLY MCFLY

Pro počáteční PoC používáme jednoduchý provozní model s jednou odpovědnou osobou.

1. Odpovědná osoba
- AI Engineer / Solution Architect.
- Odpovídá za diagnostiku, řešení výpadků a obnovení provozu.
- Spravuje Cloud Run, Cloud Tasks, Pub/Sub, Cloud SQL a externí integrace.

2. Provozní režim
- PoC nemá garantovanou podporu 24/7.
- Incidenty se řeší během plánovaného vývoje, testování a demonstračního provozu.
- Nepřetržitá dostupnost není pro PoC samostatným smluvním závazkem.

3. Kontaktování
- Google Cloud Monitoring odesílá upozornění na určený administrátorský e-mail.
- Kritické incidenty jsou označené jako CRITICAL.
- Konkrétní kontaktní adresa bude nastavena při konfiguraci GCP.
- Monitoring nesmí záviset pouze na funkčnosti testované Gmail schránky.

4. Postup při incidentu
- Přijmout alert.
- Identifikovat dotčenou komponentu.
- Dohledat související job_id a correlation_id.
- Omezit další selhání nebo duplicitní odesílání.
- Odstranit příčinu.
- Obnovit bezpečné zpracování.
- Ověřit funkčnost pomocí testovacího e-mailu.

5. Eskalace
- Chyba vlastní aplikace: AI Engineer.
- Problém služby Google Cloud: dostupné Google Cloud Support kanály.
- Bezpečnostní incident: Security Owner.
- Incident s osobními údaji: příslušný správce údajů.

6. Budoucí produkční provoz
- Určit provozního vlastníka a jeho zástupce.
- Definovat podporované hodiny a reakční SLA.
- Zavést incidentní eskalaci.
- Ověřit dostupnost notifikačních kanálů.

Cíl: Zajistit jednoznačnou odpovědnost za provoz PoC bez vytváření nepřiměřeně složitého on-call systému.

### Jak postupovat při 5xx spike, pomalé DB a pádu závislosti?

- ID: incident_runbook (povinné)
- Stav: **PŘEDPOKLAD**

INCIDENT RUNBOOK – REPLY MCFLY

Použijeme jednoduchý provozní postup pro diagnostiku a řešení nejčastějších incidentů.

1. Zvýšený počet HTTP 5xx

Detekce:
- Cloud Monitoring identifikuje zvýšenou chybovost Cloud Run endpointů.
- Cloud Logging umožní dohledat dotčené job_id a error_code.

Postup:
- Určit, zda selhává Ingress, Worker nebo externí služba.
- Zkontrolovat poslední Cloud Run deployment.
- Zkontrolovat HTTP timeouty, paměť a počet instancí.
- Zkontrolovat chyby Gmail API, Gemini a PostgreSQL.
- Při chybě nové verze vrátit předchozí kompatibilní Cloud Run revizi.
- Ověřit bezpečné opakování nedokončených úloh.

2. Pomalá nebo nedostupná PostgreSQL

Detekce:
- Zvýšená latence SQL dotazů.
- Vysoké CPU nebo počet připojení.
- Timeouty při rezervaci email_jobs.

Postup:
- Zkontrolovat Cloud SQL metriky a dostupnost.
- Identifikovat pomalé dotazy.
- Zkontrolovat databázové zámky a počet spojení.
- Použít EXPLAIN ANALYZE v bezpečném testovacím prostředí.
- Při přetížení snížit Cloud Tasks concurrency.
- Po obnově ověřit lease, checkpointy a outbox.

3. Výpadek Gmail API nebo Gemini

Detekce:
- Opakované HTTP 429, 5xx nebo timeouty.
- Zvýšený počet RETRY_PENDING a FAILED úloh.

Postup:
- Ověřit dostupnost závislosti a API kvóty.
- Zkontrolovat OAuth nebo IAM autentizaci.
- Omezit souběžnost a počet opakovaných volání.
- Použít exponential backoff.
- Nepředstírat úspěšnou AI odpověď.
- Po obnově zpracovat čekající úlohy.

4. Selhání Cloud Tasks nebo Pub/Sub

Postup:
- Zkontrolovat stav front, doručování a autentizaci.
- Ověřit, zda jsou nové zprávy evidovány v PostgreSQL.
- Zkontrolovat Gmail historyId checkpoint.
- Spustit řízenou recovery synchronizaci.
- Zabránit duplicitnímu zpracování.

5. Nejasný výsledek Gmail Send

Postup:
- Převést úlohu do DELIVERY_UNKNOWN.
- Neopakovat automaticky odeslání.
- Dohledat odpověď v Gmailu podle stabilního RFC Message-ID a dalších ověřených údajů.
- Pokud nelze výsledek spolehlivě určit, vyžádat ruční kontrolu.
- Aktualizovat databázový stav.

6. Ověření obnovy
- Zkontrolovat dostupnost Cloud Run a PostgreSQL.
- Zkontrolovat Cloud Tasks fronty.
- Odeslat syntetický testovací e-mail.
- Ověřit odpověď ve správném vlákně.
- Zkontrolovat nepřítomnost duplicit.
- Změřit end-to-end latenci.
- Zdokumentovat incident a nápravná opatření.

Cíl: Obnovit bezpečný provoz bez ztráty zpráv, nekontrolovaných retry nebo duplicitních odpovědí.

Runbook bude uložen v docs/operations/runbook.md.

### Kdy a jak ověříš obnovu ze zálohy proti RTO/RPO?

- ID: recovery_drill (povinné)
- Stav: **PŘEDPOKLAD**

DISASTER RECOVERY DRILL – REPLY MCFLY

Pro PoC provedeme alespoň jeden řízený test obnovy Cloud SQL PostgreSQL a následné synchronizace s Gmailem.

1. Cíl testu
- Ověřit obnovitelnost databázového stavu.
- Ověřit zachování integrity email_jobs a email_outbox.
- Ověřit správné obnovení Gmail synchronizace.
- Zabránit duplicitním odpovědím po obnově.

2. RTO – Recovery Time Objective
- Maximální přijatelná doba obnovy provozu.
- Konkrétní hodnota zatím není stanovena.
- Skutečný čas obnovy změříme během recovery testu.

3. RPO – Recovery Point Objective
- Maximální přijatelná ztráta dat vyjádřená časem.
- Závisí na nastavení Cloud SQL záloh a PITR.
- Konkrétní hodnota zatím není potvrzena.
- Obnovený databázový stav porovnáme s dostupnými Gmail údaji.

4. Příprava testu
- Použít izolovanou testovací databázi.
- Vytvořit syntetické email_jobs, outbox a RAG dokumenty.
- Ověřit dostupnost zálohy.
- Zaznamenat čas zahájení testu.

5. Obnova
- Obnovit Cloud SQL ze zálohy do oddělené instance.
- Ověřit databázové schéma a Alembic verzi.
- Zkontrolovat primární a cizí klíče.
- Zkontrolovat email_jobs, email_outbox a mailbox_sync_state.
- Ověřit RAG dokumenty a jejich embeddingy.

6. Gmail reconciliace
- Porovnat obnovené checkpointy s aktuálními Gmail daty.
- Dohledat nové zprávy, které vznikly po záloze.
- Ověřit již odeslané odpovědi.
- Zabránit opětovnému odeslání zpráv, které byly odeslány před obnovou.
- Nejasné výsledky předat do NEEDS_REVIEW nebo DELIVERY_UNKNOWN.

7. Test obnoveného provozu
- Obnovit řízené zpracování Cloud Tasks.
- Odeslat syntetický testovací e-mail.
- Ověřit automatickou odpověď ve správném vlákně.
- Ověřit Conversation History, RAG a Web Search.
- Zkontrolovat chyby a duplicity.

8. Vyhodnocení
- Změřit skutečné RTO.
- Změřit nebo odhadnout skutečné RPO podle dostupných důkazů.
- Zaznamenat případné nedostatky.
- Upravit recovery postup.

9. Frekvence
- Jeden recovery drill před finálním předvedením PoC.
- Při budoucím produkčním provozu opakovat podle provozní politiky, například čtvrtletně.

Recovery test musí používat oddělené testovací prostředí, aby neohrozil skutečnou Gmail komunikaci.

Cíl: Doložit, že databázi a zpracování e-mailů lze po havárii obnovit bez nekontrolovaného opakování odpovědí.

### Jak definice SLI/SLO odpovídá kritickým flow?

- ID: service_slo (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kde jsou dashboardy a co ukazují?

- ID: dashboards (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak ovlivní čerpání error budget další releasy?

- ID: error_budget (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kde je alert na storage, limity API, kredity a expirace?

- ID: capacity_alerts (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak vedeš postmortem a kdo hlídá nápravná opatření?

- ID: postmortem (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jaký je support kanál a eskalační SLA?

- ID: support_process (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

## 14 · Delivery plán, tikety a závislosti

*Cíl:* Z blueprintu se stane plán malých, ověřitelných kroků.

*Gate:* První slice je vykonatelný, priority a blokery mají vlastníky.

### Jaké jsou hlavní milníky: skeleton, MVP, beta, production?

- ID: milestones (povinné)
- Stav: **PŘEDPOKLAD**

IMPLEMENTAČNÍ MILNÍKY – REPLY MCFLY

M1 – SKELETON (lokální vývoj)
- Založit Git repozitář a strukturu Python projektu.
- Vytvořit FastAPI Ingress a Worker.
- Připravit Dockerfile a Docker Compose.
- Spustit PostgreSQL s pgvector.
- Přidat SQLAlchemy a Alembic migrace.
- Vytvořit základní doménové modely a Ports & Adapters.
- Implementovat první endpoint a test zápisu do databáze.

Akceptace: Aplikace běží lokálně v Docker kontejnerech a úspěšně komunikuje s PostgreSQL.

M2 – MVP (základní e-mailové workflow)
- Implementovat Gmail OAuth a Gmail API adapter.
- Implementovat Gmail synchronizaci a Cloud Tasks adapter.
- Zprovoznit Gmail Watch, Pub/Sub a Cloud Tasks v GCP.
- Implementovat EmailOrchestrator s Gemini.
- Implementovat email_jobs, outbox a deduplikaci.
- Odeslat automatickou odpověď do původního Gmail vlákna.

Akceptace: Nový nepřečtený e-mail automaticky spustí zpracování a odešle jednu odpověď do původního vlákna.

M3 – BETA (kompletní funkční PoC)
- Implementovat Conversation History.
- Implementovat zpracování PDF, MP3, WAV, JPEG a PNG.
- Implementovat RAG nad 1–3 fiktivními dokumenty.
- Implementovat Live Web Search.
- Ověřit všechny tři pokročilé funkce samostatně i společně.
- Doplnit retry, recovery, bezpečnostní testy a monitoring.

Akceptace: Všechny povinné funkce fungují a jsou otestované v GCP PoC.

M4 – RELEASE CANDIDATE (ověření)
- Spustit automatizované unit, integration a E2E testy.
- Ověřit idempotenci, izolaci vláken a Gmail threading.
- Ověřit chybové scénáře a bezpečnostní kontroly.
- Změřit end-to-end latenci při definované zátěži.
- Doložit splnění limitu pod 120 sekund.
- Připravit finální architektonický diagram a demonstrační scénář.

Akceptace: Všechna povinná akceptační kritéria jsou splněna a doložena výsledky testů.

M5 – PRODUCTION (budoucí rozšíření)
- Schválit provozní bezpečnostní pravidla a ochranu osobních údajů.
- Ověřit zálohování, obnovu a provozní odpovědnosti.
- Zavést odpovídající produkční monitoring a release proces.
- Nasadit do samostatného produkčního prostředí, pokud bude požadováno.

Produkční provoz není podmínkou prvního cloudového PoC. PoC však musí být skutečně nasazené a funkční v GCP.

### Jak otestuješ cestu commit -> CI -> staging -> jednoduché UI/API -> DB?

- ID: walking_skeleton (povinné)
- Stav: **PŘEDPOKLAD**

WALKING SKELETON – REPLY MCFLY

Cílem je co nejdříve ověřit kompletní technickou cestu od zdrojového kódu po běžící aplikaci a databázi.

1. Git
- Založit repozitář reply-mcfly.
- Přidat Python projekt, Dockerfile, docker-compose.yml a .gitignore.
- První změny verzovat pomocí Git commitů.

2. Lokální prostředí
- Spustit docker compose up --build.
- Spustit FastAPI Ingress a Worker.
- Spustit PostgreSQL/pgvector.
- Ověřit komunikaci aplikace s databází.

3. API
- Implementovat jednoduchý GET /health endpoint pro lokální diagnostiku.
- Implementovat testovací zápis a čtení pomocí interní aplikační služby.
- Ověřit správnou HTTP odpověď.

4. Databáze
- Vytvořit první Alembic migraci.
- Založit tabulku email_jobs nebo minimální testovací datový model.
- Ověřit úspěšný zápis a načtení dat.
- Ověřit, že data přetrvají restart kontejneru.

5. CI
- GitHub Actions spustí Ruff, pytest a Docker build.
- Neúspěšný test blokuje merge.
- Úspěšný commit je identifikovatelný v CI.

6. GCP PoC
- Sestavit a publikovat Docker image do Artifact Registry.
- Nasadit aplikaci do Cloud Run.
- Ověřit autorizované HTTP volání.
- Připojit Worker k Cloud SQL PostgreSQL.
- Ověřit databázový zápis a čtení.

7. Staging
- Samostatné staging prostředí pro PoC nezavádíme.
- Úlohu staging prostředí plní izolovaný GCP PoC projekt.

8. UI
- Vlastní webový frontend není součástí projektu.
- První test používá HTTP API.
- Následný vertikální slice využívá skutečné Gmail rozhraní.

Akceptační kritéria:
- Lokální Docker prostředí funguje.
- FastAPI komunikuje s PostgreSQL.
- CI úspěšně projde.
- Stejný Docker image lze nasadit do Cloud Run.
- Cloud Run se bezpečně připojí k Cloud SQL.
- Výsledek je doložen testy a logy.

Walking Skeleton ještě nezpracovává skutečné e-maily. Jeho účelem je ověřit vývojovou, databázovou a deployment infrastrukturu.

### Jak vypadá první implementační ticket (co / proč / AC / test / done)?

- ID: first_ticket (povinné)
- Stav: **PŘEDPOKLAD**

TICKET RM-001 – LOKÁLNÍ DOCKER SKELETON

Název:
Zprovoznit základní Python/FastAPI aplikaci s PostgreSQL/pgvector v Docker Compose.

CO IMPLEMENTOVAT:
- Založit Git repozitář reply-mcfly.
- Vytvořit strukturu src/, tests/, migrations/, infra/ a docs/.
- Připravit Python 3.12 a FastAPI.
- Vytvořit Dockerfile a docker-compose.yml.
- Spustit Ingress a Worker ze stejného Docker image.
- Spustit PostgreSQL s pgvector.
- Nastavit SQLAlchemy a Alembic.
- Implementovat GET /health a ověření databázového připojení.
- Přidat .gitignore, .dockerignore a .env.example.
- Vytvořit první pytest test.

PROČ:
- Ověřit funkčnost lokálního vývojového prostředí.
- Zajistit reprodukovatelné spuštění aplikace.
- Připravit základ pro Gmail API, Gemini a AI workflow.
- Odhalit problémy s kontejnery, závislostmi a databází před integrací cloudových služeb.

AKCEPTAČNÍ KRITÉRIA:
AC-01: docker compose up --build úspěšně spustí všechny tři kontejnery.

AC-02: FastAPI Ingress a Worker odpovídají na autorizované nebo lokální diagnostické požadavky.

AC-03: PostgreSQL je dostupný a podporuje pgvector.

AC-04: Alembic upgrade head úspěšně vytvoří databázové schéma.

AC-05: Aplikace dokáže zapsat a načíst testovací databázový záznam.

AC-06: Data v PostgreSQL přetrvají restart kontejneru.

AC-07: pytest úspěšně provede základní automatické testy.

AC-08: Žádné secrets nejsou součástí Git repozitáře ani Docker image.

TESTOVÁNÍ:
- Docker Compose build a startup.
- Health check Ingress a Worker.
- PostgreSQL connectivity test.
- Alembic migration test.
- Database read/write test.
- Restart test.
- pytest unit/integration tests.

DEFINITION OF DONE:
- Všechna akceptační kritéria splněna.
- Docker Compose funguje na vývojovém počítači.
- README obsahuje ověřený postup spuštění.
- Změny jsou verzované v Git.
- Testy úspěšně prošly.
- Není nalezen žádný známý kritický bezpečnostní problém.

MIMO ROZSAH TICKETU:
- Gmail OAuth a Gmail Watch.
- Vertex AI Gemini inference.
- Conversation History, RAG a Web Search.
- Produkční GCP deployment.

Tyto funkce budou implementovány v následujících vertikálních řezech.

### Co musí být rozhodnuto/koupeno/schváleno před kódem?

- ID: delivery_dependencies (povinné)
- Stav: **PŘEDPOKLAD**

IMPLEMENTAČNÍ ZÁVISLOSTI – REPLY MCFLY

PŘED ZAHÁJENÍM LOKÁLNÍHO VÝVOJE:

1. Technické vybavení
- Funkční Docker a Docker Compose.
- Git a přístup do Git repozitáře.
- Python 3.12 pro případné lokální spuštění mimo kontejnery.
- Vývojové prostředí umožňující práci s Python kódem.

2. Architektonická rozhodnutí
- Python/FastAPI.
- Event-driven Modular Monolith + Ports & Adapters.
- PostgreSQL/pgvector.
- Google Gen AI SDK.
- Vlastní EmailOrchestrator.
- Docker Compose pro lokální vývoj.

Tato rozhodnutí jsou již součástí návrhu.

3. Lokální konfigurace
- Vytvořit .env.example.
- Definovat vývojovou databázovou konfiguraci.
- Připravit mock adaptéry externích API.
- Připravit syntetická testovací data.

PŘED REÁLNÝMI CLOUDOVÝMI INTEGRACEMI:

4. Google Cloud
- Vytvořený GCP projekt.
- Aktivované fakturační nastavení nebo dostupný trial kredit.
- Ověřené kvóty a oprávnění.
- Povolené potřebné Google Cloud API.
- Ověřená dostupnost zvoleného Gemini a embedding modelu.

5. Gmail
- Dedikovaná testovací Gmail schránka.
- OAuth consent screen a OAuth klient.
- Schválené potřebné Gmail API scopes.
- Bezpečně uložený refresh token.
- Ověřená možnost čtení a odesílání zpráv.

6. Cloud infrastruktura
- Cloud Run.
- Cloud SQL PostgreSQL.
- Pub/Sub.
- Cloud Tasks.
- Secret Manager.
- Cloud Scheduler.
- IAM servisní identity.

7. Náklady a bezpečnost
- Potvrzený dostupný GCP rozpočet.
- Ověřená cena Cloud SQL a Gemini.
- Používání syntetických testovacích dat.
- Oddělení přístupových údajů od zdrojového kódu.

CO NENÍ PODMÍNKOU PŘED PRVNÍM KÓDEM:
- Hotová CI/CD pipeline.
- Kompletní Terraform infrastruktura.
- Vlastní doména.
- Produkční SLA.
- Samostatný staging.
- LangChain, LangGraph nebo CrewAI.
- Samostatný webový frontend.

Cíl:
Zahájit lokální implementaci bez čekání na kompletní cloudovou infrastrukturu. Externí integrace připojovat postupně po ověření jejich konfigurace.

### Jaký je nejbližší přesný krok, který můžeš udělat dnes?

- ID: next_action (povinné)
- Stav: **PŘEDPOKLAD**

NEJBLIŽŠÍ KROK – REPLY MCFLY

Zahájit implementaci ticketu RM-001: Lokální Docker Skeleton.

POSTUP:

1. Založit lokální adresář projektu reply-mcfly.
2. Inicializovat Git repozitář.
3. Vytvořit základní strukturu Python aplikace.
4. Přidat pyproject.toml a potřebné Python závislosti.
5. Vytvořit Dockerfile.
6. Vytvořit docker-compose.yml se službami Ingress, Worker a PostgreSQL/pgvector.
7. Přidat .gitignore, .dockerignore a .env.example.
8. Implementovat jednoduchý FastAPI health endpoint.
9. Nakonfigurovat SQLAlchemy a Alembic.
10. Spustit docker compose up --build.
11. Ověřit komunikaci s databází.
12. Spustit první pytest test.
13. Zaznamenat výsledek do README a vytvořit Git commit.

OČEKÁVANÝ VÝSLEDEK:
- Tři funkční Docker kontejnery.
- FastAPI Ingress a Worker.
- PostgreSQL/pgvector.
- Funkční databázové připojení.
- První úspěšné automatické testy.
- Reprodukovatelný lokální postup spuštění.

NÁSLEDUJÍCÍ KROK:
Implementovat Gmail adapter a první skutečný e-mailový workflow.

DŮLEŽITÉ:
První úspěch měříme funkčním lokálním prostředím, nikoliv množstvím napsaného kódu. Cloudové integrace připojíme postupně, aniž bychom měnili potvrzenou architekturu.

### Jaké jsou další malé vertikální řezy a jejich pořadí?

- ID: backlog (doplňkové)
- Stav: **PŘEDPOKLAD**

IMPLEMENTAČNÍ BACKLOG – REPLY MCFLY

RM-001 – Lokální Docker Skeleton
- FastAPI, Docker Compose, PostgreSQL/pgvector, Alembic.
- Výsledek: Funkční lokální vývojové prostředí.

RM-002 – Gmail API Adapter
- OAuth 2.0.
- Načtení testovací zprávy a příloh.
- Načtení Gmail vlákna.
- Výsledek: Ověřené Gmail API připojení.

RM-003 – Gemini Adapter
- Google Gen AI SDK.
- Volání Gemini přes Vertex AI.
- Zpracování textu a strukturované odpovědi.
- Výsledek: Funkční AI inference.

RM-004 – Email Processing Service
- Evidence email_jobs.
- Atomické rezervace a stavový automat.
- Základní EmailOrchestrator.
- Výsledek: Lokální zpracování e-mailu.

RM-005 – Gmail Reply + Outbox
- Kontrola příjemce.
- RFC Message-ID a threading hlavičky.
- Bezpečné odeslání.
- Ochrana proti duplicitám.
- Výsledek: Odpověď ve správném Gmail vlákně.

RM-006 – Cloud Infrastructure
- Artifact Registry.
- Cloud Run Ingress a Worker.
- Cloud SQL.
- Pub/Sub, Cloud Tasks, Secret Manager a Scheduler.
- Výsledek: Připravené GCP PoC prostředí.

RM-007 – Gmail Watch + Automatic Processing
- Gmail Watch notifikace.
- Pub/Sub → Ingress → Sync Queue.
- Gmail History synchronizace.
- Process Queue → Worker.
- Výsledek: Automatické zpracování nových nepřečtených e-mailů.

RM-008 – Conversation History
- Gmail Threads API.
- Výběr relevantních předchozích zpráv.
- Token budget a izolace vláken.
- Výsledek: Správné navazující odpovědi.

RM-009 – Multimodal Attachments
- PDF, MP3, WAV, JPEG a PNG.
- Validace a interpretace.
- Limity a chybové scénáře.
- Výsledek: Ověřené zpracování všech pěti formátů.

RM-010 – RAG
- Import 1–3 fiktivních dokumentů.
- Chunking a embeddingy.
- PostgreSQL/pgvector retrieval.
- Výsledek: Odpovědi založené na znalostní bázi.

RM-011 – Live Web Search
- Detekce časově závislých dotazů.
- Google Search grounding.
- Ověření aktuálnosti a relevantních zdrojů.
- Výsledek: Aktuální odpovědi bez vymýšlení faktů.

RM-012 – Combined AI Workflow
- Conversation History + RAG + Web Search.
- Výběr relevantních zdrojů.
- Strukturovaný návrh odpovědi.
- Výsledek: Všechny tři pokročilé schopnosti fungují společně.

RM-013 – Reliability & Recovery
- Retry, dedup, lease a DELIVERY_UNKNOWN.
- Obnova Gmail Watch.
- Recovery nedokončených úloh.
- Výsledek: Bezpečné zpracování při chybách a duplicitách.

RM-014 – Monitoring & Performance
- Strukturované logy.
- Correlation IDs.
- Latence jednotlivých komponent.
- Měření end-to-end času.
- Výsledek: Prokazatelné měření limitu pod 120 sekund.

RM-015 – Security & Acceptance Tests
- Unit, integration a E2E testy.
- Testování prompt injection a neplatných příloh.
- Test souběžnosti a opakovaného doručení.
- Test všech tří pokročilých schopností.
- Výsledek: Splněná akceptační kritéria.

RM-016 – Final Demo & Documentation
- Aktualizovaný architektonický diagram.
- ADR a README.
- Výsledky testů a metrik.
- 10–15minutová prezentace.
- Výsledek: Funkční, zdokumentované a obhajitelné cloudové PoC.

PRAVIDLO IMPLEMENTACE:
Každý ticket musí mít jasný výsledek, akceptační kritéria a testy. Po dokončení důležitého vertikálního řezu se ověří funkčnost před zahájením dalšího.

Pořadí minimalizuje riziko integrací a umožňuje průběžně testovat celý systém. Nezavádíme LangGraph, mikroservisy ani další infrastrukturu bez konkrétní potřeby.

### Jaké jsou hrubé odhady a kde je největší nejistota?

- ID: estimates (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jaké technické experimenty ověří nejasné předpoklady?

- ID: spikes (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kdo píše frontend, backend, infra, QA, UX a security review?

- ID: team_roles (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jaké údaje musí obsahovat ready ticket?

- ID: definition_ready (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Co přesně znamená Done včetně dokumentace?

- ID: definition_done (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jaká jsou top rizika, pravděpodobnost, dopad a mitigace?

- ID: risk_register (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kde vedeš ADR a změny architektonických rozhodnutí?

- ID: decision_log (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak se řeší změna zadání během implementace?

- ID: change_management (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

## 15 · Production release, provozní předání a úspěch

*Cíl:* Go-live je změna provozu, ne jen zelený build.

*Gate:* Před releasem existuje schválený, ověřený rollback a monitoring; po releasu ověřené výsledky.

### Kdo schválí produkční release a kdo je na místě při nasazení?

- ID: release_owner (povinné)
- Stav: **PŘEDPOKLAD**

RELEASE OWNERSHIP – REPLY MCFLY

1. Odpovědná osoba
- AI Engineer / Solution Architect.
- Odpovídá za přípravu, testování, schválení a nasazení PoC.
- Kontroluje výsledky CI, bezpečnostní nálezy a stav infrastruktury.

2. Schválení PoC release
- Všechny povinné testy musí úspěšně projít.
- Musí být ověřeny Conversation History, RAG a Live Web Search.
- Musí fungovat PDF, MP3, WAV, JPEG a PNG přílohy.
- Musí být prokázáno správné Gmail threading a prevence duplicit.
- Musí být doložena end-to-end latence pod 120 sekund v definovaných testech.

3. Přítomnost při nasazení
- AI Engineer provádí deployment.
- Kontroluje Cloud Run, Cloud Tasks, Pub/Sub, Cloud SQL a Gemini.
- Po nasazení spouští smoke a E2E testy.
- Sleduje logy a případné incidenty.

4. Produkční release
- Před skutečným produkčním provozem musí být určen provozní vlastník.
- Produkční schválení musí zahrnovat bezpečnost, ochranu dat, zálohování a recovery.
- Automatický produkční deployment bez schválení zatím nepoužíváme.

5. Evidence
- Git commit a release tag.
- Docker image digest.
- Výsledky CI a E2E testů.
- Datum nasazení.
- Odpovědná osoba.
- Výsledek smoke testů.

Pro PoC je schvalovatelem i realizátorem nasazení AI Engineer / Solution Architect. Pro budoucí produkční prostředí bude nutné stanovit formální schvalovací proces.

### Jaký je přesný postup nasazení včetně pořadí migrací?

- ID: release_plan (povinné)
- Stav: **PŘEDPOKLAD**

RELEASE PLAN – REPLY MCFLY

1. Příprava release
- Ověřit úspěšný CI pipeline.
- Ověřit požadované testy a bezpečnostní kontroly.
- Identifikovat Git commit a Docker image.
- Zkontrolovat změny databázového schématu.

2. Build
- Sestavit Docker image z konkrétního commitu.
- Ověřit bezpečnost image.
- Publikovat image do Google Artifact Registry.
- Zaznamenat image digest.

3. Infrastructure
- Ověřit Cloud Run, Cloud SQL, Pub/Sub, Cloud Tasks a IAM.
- Ověřit dostupnost Secret Manageru.
- Ověřit Gemini a Gmail OAuth konfiguraci.
- Případné změny infrastruktury provést řízeně přes Terraform.

4. Databáze – před aplikací
- Ověřit dostupnost zálohy Cloud SQL.
- Ověřit kompatibilitu databázové migrace.
- Spustit Alembic upgrade head jako samostatný řízený krok.
- Ověřit úspěšné dokončení migrace.
- Migrace musí být zpětně kompatibilní se současnou verzí aplikace.

5. Deployment Cloud Run
- Nasadit stejný Docker image do Ingress a Workeru.
- Použít odpovídající environment variables a secrets.
- Nastavit správné servisní identity.
- Ověřit Cloud Run IAM/OIDC.
- Přepnout provoz až po ověření kompatibility nových revizí.

6. Post-deployment kontroly
- Ověřit dostupnost aplikace.
- Ověřit připojení Cloud SQL.
- Ověřit Pub/Sub a Cloud Tasks.
- Ověřit Gmail synchronizaci.
- Odeslat syntetický testovací e-mail.
- Ověřit odpověď ve správném vlákně.
- Zkontrolovat logy a latenci.

7. Aktivace provozu
- Povolovat skutečné zpracování až po úspěšných smoke testech.
- Ověřit, že nevznikají duplicitní odpovědi.
- Zkontrolovat čekající úlohy a stav outboxu.

8. Rollback
- Při chybě zastavit další rizikové zpracování.
- Vrátit předchozí kompatibilní Cloud Run revizi.
- Zkontrolovat stav databáze a outboxu.
- Obnovit zpracování až po úspěšné kontrole.

9. Evidence
- Release verze a image digest.
- Výsledky migrací.
- Výsledky smoke a E2E testů.
- Naměřená latence.
- Rozhodnutí o schválení release.

Cíl: Reprodukovatelné nasazení bez ztráty stavu zpracování a bez duplicitního odesílání odpovědí.

### Jaké předrelease kontrolní body musí být doložené?

- ID: preflight_checklist (povinné)
- Stav: **PŘEDPOKLAD**

PREFLIGHT CHECKLIST – REPLY MCFLY

1. Zdrojový kód
- Změny jsou verzované v Git.
- Release je navázán na konkrétní commit.
- CI pipeline úspěšně dokončil povinné kontroly.
- Docker image je identifikován digestem.

2. Automatizované testy
- Unit tests: PASS.
- Integration tests: PASS.
- Contract tests: PASS.
- Security tests: PASS.
- End-to-end tests: PASS.

3. Funkční požadavky
- Automatická detekce nových nepřečtených zpráv.
- Správné Gmail threading.
- PDF, MP3, WAV, JPEG a PNG.
- Conversation History.
- RAG nad 1–3 fiktivními dokumenty.
- Live Web Search.
- Kombinace všech tří pokročilých funkcí.
- Prevence duplicit a e-mailových smyček.

4. Databáze
- Cloud SQL je dostupné.
- Alembic migrace byly ověřeny.
- UNIQUE constraints a stavový automat fungují.
- Outbox a lease byly otestovány.
- Je dostupná ověřená záloha před rizikovou migrací.

5. GCP infrastruktura
- Cloud Run Ingress a Worker jsou správně nakonfigurovány.
- Pub/Sub doručuje notifikace.
- Cloud Tasks úspěšně spouští úlohy.
- Secret Manager a IAM fungují.
- Gmail OAuth a Gemini API jsou dostupné.
- Cloud Scheduler má správné maintenance nastavení.

6. Bezpečnost
- Žádné secrets v Git nebo Docker image.
- Neautorizované požadavky jsou odmítnuty.
- Přílohy mají validaci a limity.
- Prompt injection testy prošly.
- Logy neobsahují citlivé informace.
- Kritické bezpečnostní nálezy jsou vyřešeny.

7. Výkon a provoz
- Naměřené end-to-end zpracování pod 120 sekund.
- Ověřená idempotence.
- Ověřené retry a recovery.
- Nakonfigurované základní alerty.
- Zkontrolovaný GCP rozpočet.

8. Release evidence
- Identifikátor release.
- Výsledky CI a E2E.
- Docker image digest.
- Výsledek migrací.
- Schválení AI Engineerem.

Pokud není splněno některé povinné kritérium, release není možné označit za dokončené PoC.

### Jaké smoke testy se provedou bezprostředně po deploy?

- ID: smoke_tests (povinné)
- Stav: **PŘEDPOKLAD**

POST-DEPLOYMENT SMOKE TESTS – REPLY MCFLY

1. Cloud Run
- Ověřit, že Ingress i Worker mají aktivní správnou revizi.
- Ověřit dostupnost interního health endpointu.
- Ověřit, že IAM/OIDC blokuje neautorizované požadavky.

2. PostgreSQL
- Ověřit databázové připojení.
- Ověřit aktuální Alembic verzi.
- Ověřit dostupnost tabulek email_jobs, email_outbox a mailbox_sync_state.

3. Cloud Tasks a Pub/Sub
- Ověřit příjem testovací notifikace.
- Ověřit vytvoření synchronizační úlohy.
- Ověřit vytvoření a zpracování Process Queue úlohy.

4. Gmail API
- Ověřit platnost OAuth autorizace.
- Odeslat nový syntetický testovací e-mail.
- Ověřit automatickou detekci.
- Ověřit odpověď ve stejném Gmail vlákně.

5. Vertex AI Gemini
- Ověřit úspěšnou AI inference.
- Ověřit platný strukturovaný výstup.
- Ověřit bezpečnou validaci návrhu odpovědi.

6. Conversation History
- Odeslat navazující zprávu.
- Ověřit použití relevantní historie stejného vlákna.

7. RAG
- Odeslat známý dotaz na fiktivní produkt.
- Ověřit použití schválených RAG faktů.

8. Live Web Search
- Odeslat dotaz vyžadující aktuální veřejné informace.
- Ověřit skutečné vyhledávání a použití zdrojů.

9. Idempotence
- Simulovat opakované doručení úlohy.
- Ověřit, že nevznikne druhá automatická odpověď.

10. Monitoring
- Ověřit vznik strukturovaných logů.
- Ověřit job_id a correlation_id.
- Změřit end-to-end latenci.
- Zkontrolovat nepřítomnost kritických chyb.

Smoke testy představují rychlou kontrolu po nasazení. Kompletní regresní, bezpečnostní a zátěžové testy se provádějí odděleně před release.

### Které metriky či chyby spustí okamžitý rollback?

- ID: rollback_trigger (povinné)
- Stav: **PŘEDPOKLAD**

ROLLBACK TRIGGERS – REPLY MCFLY

Rollback nebo okamžité pozastavení zpracování se spouští při kritickém selhání nově nasazené verze.

1. Kritické funkční chyby
- Potvrzené duplicitní odeslání automatické odpovědi.
- Odeslání odpovědi nesprávnému příjemci.
- Smíchání Conversation History mezi nesouvisejícími vlákny.
- Neoprávněná akce vyvolaná obsahem e-mailu nebo prompt injection.

2. Bezpečnostní incident
- Potvrzený únik secrets nebo osobních údajů.
- Neautorizovaný přístup k Gmailu nebo databázi.
- Obejití IAM/OIDC bezpečnostních kontrol.
- Nekontrolované odesílání soukromých dat do externího vyhledávání.

3. Kritické provozní chyby
- Nová verze nedokáže zpracovávat příchozí zprávy.
- Opakované HTTP 5xx způsobené novým deploymentem.
- Závažná chyba databázové migrace.
- Nekonzistentní stavy email_jobs nebo email_outbox.

4. Výkonnost
- Nová verze opakovaně překračuje 120sekundový end-to-end limit v definované zátěži.
- Výrazný nárůst čekání ve frontách způsobený novým deploymentem.
- Kritické zvýšení Gemini nebo databázové latence po změně aplikace.

5. Postup
- Pozastavit další rizikové zpracování nebo odesílání.
- Vyhodnotit, zda je příčinou deployment nebo externí závislost.
- Při chybě nové verze vrátit předchozí kompatibilní Cloud Run revizi.
- Ověřit stav databáze, lease a outboxu.
- Spustit smoke testy.
- Obnovit zpracování pouze po ověření bezpečnosti.

6. Rozlišení
- Výpadek Gmail API nebo Gemini nemusí být vyřešen rollbackem.
- V takovém případě je vhodnější retry, omezení souběžnosti nebo dočasné pozastavení.
- Rollback nesmí zhoršit databázovou konzistenci.

7. Evidence
- Čas a příčina rollbacku.
- Dotčená Cloud Run revize.
- Původní a obnovený image digest.
- Výsledky kontrolních testů.
- Stav nedokončených úloh.

Cíl: Při kritickém incidentu zabránit dalším škodám a bezpečně obnovit poslední známou funkční verzi.

### Kdy byl naposledy odzkoušen návrat/obnova a jaký je důkaz?

- ID: rollback_exercise (povinné)
- Stav: **PŘEDPOKLAD**

ROLLBACK EXERCISE – REPLY MCFLY

Aktuální stav:
- Rollback ani disaster recovery dosud nebyly provedeny.
- Neexistuje ověřený výsledek návratu na předchozí Cloud Run revizi.
- Neexistuje doložený test obnovení databáze ze zálohy.

Plán ověření:

1. Rollback aplikace
- Nasadit funkční verzi aplikace do GCP PoC.
- Zaznamenat její image digest a Cloud Run revizi.
- Nasadit testovací revizi se simulovanou chybou.
- Vrátit provoz na předchozí kompatibilní revizi.
- Ověřit funkčnost FastAPI, Gmail synchronizace a zpracování e-mailu.

2. Ověření databáze
- Zkontrolovat kompatibilitu Alembic migrací.
- Ověřit, že předchozí aplikace dokáže používat aktuální schéma.
- Zkontrolovat email_jobs, email_outbox a mailbox_sync_state.
- Ověřit, že rollback nevytvořil duplicitní odpovědi.

3. Obnova ze zálohy
- Použít oddělenou testovací Cloud SQL instanci.
- Obnovit databázi ze zálohy.
- Ověřit integritu dat a RAG dokumentů.
- Provést Gmail reconciliaci v bezpečném testovacím režimu.

4. Funkční ověření
- Odeslat syntetický testovací e-mail.
- Ověřit automatickou odpověď ve správném vlákně.
- Ověřit Conversation History, RAG a Web Search.
- Zkontrolovat retry, deduplikaci a monitoring.

5. Evidence
- Datum a čas testu.
- Identifikátor původní a nové Cloud Run revize.
- Git commit a Docker image digest.
- Verze databázového schématu.
- Naměřená doba obnovy.
- Výsledky smoke a E2E testů.
- PASS/FAIL a zjištěné nedostatky.

6. Frekvence
- Minimálně jeden rollback/recovery test před finálním PoC release.
- Při budoucím produkčním provozu opakovat podle schváleného provozního plánu.

Plánovaný dokument:
docs/operations/rollback-test.md

Cíl:
Prokázat schopnost bezpečně vrátit aplikaci na poslední funkční verzi a obnovit databázi bez nekontrolovaného opakování již odeslaných odpovědí.

Dokument je plánovaný výstup, nikoliv již existující důkaz.

### Kdo má přístup do produkce a jak se auditují změny?

- ID: production_access (povinné)
- Stav: **PŘEDPOKLAD**

PRODUCTION ACCESS & AUDIT – REPLY MCFLY

1. Přístup do GCP PoC
- Primární správce: AI Engineer / Solution Architect.
- Přístup je řízen pomocí Google Cloud IAM.
- Každá servisní identita má pouze potřebná oprávnění.
- Nevyužíváme sdílené administrátorské účty.

2. Servisní identity
- Cloud Run Ingress: příjem Pub/Sub notifikací a vytvoření synchronizačních úloh.
- Cloud Run Worker: přístup ke Gmail API, Cloud SQL, Gemini a potřebným secrets.
- Pub/Sub a Cloud Tasks: autorizované volání interních Cloud Run endpointů.
- CI/CD identita: sestavení a nasazení aplikace s omezenými oprávněními.
- Migrační identita: provádění databázových migrací.

3. Administrátorská oprávnění
- Přístup pouze pro určeného správce prostředí.
- MFA pro administrátorské přihlášení.
- Preferovat předdefinované nebo vlastní IAM role s minimálními oprávněními.
- Nepoužívat dlouhodobé klíče servisních účtů, pokud to není nezbytné.

4. Audit změn
- Google Cloud Audit Logs pro administrativní události.
- Git historie a Pull Requests pro změny zdrojového kódu.
- GitHub Actions pro historii CI/CD.
- Cloud Run revize a image digest pro identifikaci nasazené verze.
- Alembic migrace pro změny databázového schématu.
- Secret Manager audit pro přístupy a změny secrets podle zapnutých auditních kategorií.

5. Evidence změn
- Kdo změnu provedl.
- Kdy byla provedena.
- Který prostředek byl změněn.
- Git commit nebo release ID.
- Výsledek deploymentu.
- Případný rollback nebo incident.

6. Produkční prostředí
- Samostatná produkce zatím není vytvořena.
- Před jejím zavedením budou schváleny role, přístupová politika a provozní odpovědnosti.
- Produkční credentials a databáze budou oddělené od PoC.

Cíl: Zajistit dohledatelné změny a minimalizovat riziko neoprávněného přístupu bez budování vlastního systému správy identit.

### Jaké dashboardy a alerty sleduješ prvních 24–72 h?

- ID: launch_monitoring (povinné)
- Stav: **PŘEDPOKLAD**

POST-LAUNCH MONITORING – REPLY MCFLY

Po nasazení PoC budeme sledovat Cloud Monitoring, Cloud Logging a stav zpracování v PostgreSQL.

1. End-to-end performance
- Doba od přijetí e-mailu po potvrzené Gmail Send.
- p50, p95 a jednotlivé překročené úlohy.
- Cílová latence: pod 120 sekund.
- Latence Gmail synchronizace, fronty, příloh, RAG, Web Search a Gemini.

2. Email processing dashboard
- Počet nových přijatých zpráv.
- Počet zpracovaných email jobs.
- Počet SENT, FAILED, RETRY_PENDING a NEEDS_REVIEW.
- Počet DELIVERY_UNKNOWN.
- Počet přeskočených a duplicitních zpráv.
- Počet čekajících úloh.

3. Cloud Run
- Počet aktivních instancí.
- CPU a paměť.
- Concurrency.
- HTTP 4xx/5xx a timeouty.
- Cold start a doba zpracování.

4. Cloud Tasks a Pub/Sub
- Stáří nejstarší úlohy.
- Počet čekajících úloh.
- Počet neúspěšných dispatch pokusů.
- Chyby Pub/Sub push doručování.
- Stav Gmail Watch a jeho expirace.

5. Cloud SQL
- Dostupnost databáze.
- CPU, paměť a disk.
- Počet databázových spojení.
- Latence kritických SQL dotazů.
- Chyby transakcí a rezervací.

6. AI a externí API
- Gemini inference latency.
- Počet chyb a HTTP 429.
- Spotřeba tokenů.
- Úspěšnost RAG retrieval.
- Úspěšnost Live Web Search.
- Selhání Gmail API.

7. Náklady
- Cloud Run a Cloud SQL spotřeba.
- Vertex AI Gemini a grounding.
- Počet AI volání na email job.
- Billing Budget upozornění.

8. Alerty
- WARNING: end-to-end p95 nad 90 sekund v definovaném okně.
- CRITICAL: potvrzená úloha nad 120 sekund.
- WARNING: nejstarší čekající úloha nad 30 sekund.
- CRITICAL: nedostupný PostgreSQL nebo nemožnost odeslat odpověď.
- CRITICAL: potvrzené duplicitní odeslání nebo bezpečnostní incident.

9. Časový režim
- První 24 hodin: kontrola po deploymentu a během plánovaných testů.
- Do 72 hodin: vyhodnocení stability, nákladů a chyb.
- PoC nemá nepřetržitou 24/7 on-call službu.

10. Evidence
- Cloud Monitoring dashboard.
- Cloud Logging podle job_id.
- Výsledky E2E testů.
- Přehled incidentů a nápravných opatření.

Cíl: Včas odhalit chyby nové verze, problémy s API kvótami, přetížení front a překročení 120sekundového limitu.

### Kdy ověříš úspěšnost proti produktovému cíli?

- ID: post_launch_metrics (povinné)
- Stav: **PŘEDPOKLAD**

POST-LAUNCH SUCCESS METRICS – REPLY MCFLY

Hlavním cílem je automatické, bezpečné a přesné zpracování e-mailů s odpovědí do 120 sekund.

1. Okamžité ověření – po deploymentu
- Spustit základní smoke test.
- Odeslat syntetický testovací e-mail.
- Ověřit automatickou odpověď ve správném vlákně.
- Ověřit Cloud Run, Cloud Tasks, Pub/Sub a Cloud SQL.
- Zkontrolovat logy a latenci.

2. Funkční ověření – v rámci UAT
- Automatická detekce nových nepřečtených zpráv.
- Správné zpracování PDF, MP3, WAV, JPEG a PNG.
- Conversation History ve stejném vlákně.
- Izolace nezávislých vláken.
- RAG založený na 1–3 fiktivních dokumentech.
- Live Web Search s aktuálními zdroji.
- Kombinace všech tří pokročilých funkcí.
- Správné Gmail threading.
- Deduplikace a prevence e-mailových smyček.

3. Výkonnostní ověření
- Měřit čas od přijetí zprávy po potvrzené odeslání.
- Cíl: méně než 120 sekund.
- Vyhodnotit p50, p95, maximum a počet překročení.
- Testovat jednoduché i multimodální zprávy.
- Testovat současné přijetí více e-mailů.

4. Spolehlivost
- Cílový počet duplicitně odeslaných odpovědí: 0.
- Cílový počet ztracených zpráv: 0.
- Všechny testované chybové scénáře musí mít očekávaný výsledek.
- DELIVERY_UNKNOWN nesmí vést k nekontrolovanému opakování odeslání.

5. Vyhodnocení po 24 hodinách
- Zkontrolovat dostupnost služeb.
- Zkontrolovat neúspěšné úlohy a retry.
- Zkontrolovat latenci.
- Zkontrolovat neočekávané náklady.
- Ověřit Gmail Watch a synchronizační checkpoint.

6. Vyhodnocení po 72 hodinách
- Vyhodnotit stabilitu testovacího provozu.
- Porovnat výsledky s akceptačními kritérii.
- Identifikovat výkonnostní bottlenecky.
- Zdokumentovat zbývající technická rizika.
- Rozhodnout, zda je PoC připravené k finální demonstraci.

7. Finální akceptace
- Povinné funkce musí být ověřeny testy.
- Měření musí doložit splnění časového limitu v definovaných podmínkách.
- Bezpečnostní a kritické funkční chyby nesmějí zůstat otevřené.
- Výsledky budou součástí závěrečné technické dokumentace a prezentace.

DŮLEŽITÉ:
Časový limit pod 120 sekund je požadavek na skutečný end-to-end proces. Nestačí změřit pouze dobu generování odpovědi modelem.

Cíl: Prokázat splnění funkčních a výkonnostních požadavků na základě měřitelných výsledků, nikoliv pouze úspěšného deploymentu.

### Budeš dělat canary, pilot, feature flag nebo postupné spuštění?

- ID: feature_rollout (doplňkové)
- Stav: **PŘEDPOKLAD**

Pilot

### Jak informuješ zákazníky, support a interní týmy?

- ID: customer_comms (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kde je nouzový kontakt, on-call, dodavatelé a rollback owner?

- ID: incident_contacts (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kde budou provozní přístupy, runbook, ADR a diagramy?

- ID: production_docs (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak po migraci vypneš staré systémy a smažeš přebytečná data?

- ID: decommission (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jaké provozní předání a školení je potřeba?

- ID: handover (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

## 16 · Doplňující návrh: AI / LLM / ML

*Cíl:* AI systém vyžaduje měřitelnou kvalitu, ochranu vstupů a řízení nákladů.

*Gate:* Eval dataset, kvalita, bezpečnost, prompty a fallback jsou ověřené.

### Kde přesně AI rozhoduje/generuje a proč nestačí deterministické řešení?

- ID: ai_use_case (povinné)
- Stav: **PŘEDPOKLAD**

AI USE CASE – REPLY MCFLY

1. Úloha umělé inteligence
- Porozumění přirozenému jazyku příchozích e-mailů.
- Interpretace PDF, MP3, WAV, JPEG a PNG příloh.
- Porozumění předchozí komunikaci v aktuálním vlákně.
- Posouzení potřeby RAG a Live Web Search.
- Syntéza relevantních informací z dostupných zdrojů.
- Generování srozumitelné odpovědi.

2. Co řeší AI
- Extrakce významu a informací z nestrukturovaného obsahu.
- Interpretace multimodálních vstupů.
- Sémantické posouzení relevance kontextu.
- Vytvoření návrhu odpovědi na základě faktů z e-mailu, historie, RAG a webu.

3. Co řeší deterministický backend
- Gmail OAuth a API komunikaci.
- Identifikaci zpráv a vláken.
- Deduplikaci a stavový automat.
- Validaci souborů a bezpečnostních limitů.
- Řízení přístupu k databázi a externím API.
- Kontrolu příjemce a Gmail threading hlaviček.
- Odesílání odpovědí a recovery.

4. Proč nestačí deterministické řešení
- E-maily obsahují neomezené varianty přirozeného jazyka.
- Dotazy mohou obsahovat více souvisejících požadavků.
- Přílohy mohou obsahovat obrazové nebo zvukové informace.
- Navazující dotazy vyžadují pochopení kontextu.
- Odpověď musí kombinovat informace z více zdrojů.

Pravidlový systém by vyžadoval velké množství předem definovaných scénářů a nedokázal by dostatečně flexibilně zpracovat neznámé dotazy.

5. AI orchestrace
- EmailOrchestrator řídí deterministický workflow.
- AI pomáhá určit informační potřeby a vytvořit odpověď.
- Aplikace kontroluje, které nástroje může použít.
- Gemini neprovádí přímo Gmail Send ani databázové administrativní operace.

6. Rozšiřitelnost
- WorkflowRunner odděluje orchestraci od jednotlivých AI schopností.
- Při výrazném rozšíření lze implementovat LangGraph.
- Pro současné PoC není další agentní framework nutný.

PRINCIP:
AI používáme tam, kde je nutné porozumění nestrukturovaným informacím. Kritické bezpečnostní, databázové a integrační operace zůstávají deterministické.

### Jaký model/provider/verzi smíš použít a kde se zpracují data?

- ID: ai_provider (povinné)
- Stav: **PŘEDPOKLAD**

AI PROVIDER A MODEL – REPLY MCFLY

1. Poskytovatel
- Google Cloud – Vertex AI Gemini.
- Integrace pomocí oficiálního Google Gen AI SDK (google-genai).
- Autentizace prostřednictvím Google Cloud IAM a Application Default Credentials.

2. Výběr modelu
- Preferujeme rychlý a cenově efektivní multimodální Gemini Flash model.
- Model musí podporovat text, PDF, obrázky a audio vstupy potřebné pro PoC.
- Musí umožňovat strukturovaný výstup a požadovaný Google Search grounding.
- Konkrétní model ID a verze budou potvrzeny podle aktuální dostupnosti a integračních testů.
- Pro nasazení použijeme explicitně nakonfigurovaný model ID, nikoliv automaticky vybíraný model.

3. Embedding model
- Pro RAG použijeme podporovaný embedding model dostupný přes Vertex AI.
- Embeddingy budou uloženy v PostgreSQL/pgvector.
- ID modelu, dimenze embeddingů a jejich verze se budou evidovat.
- Změna embedding modelu vyžaduje ověření kompatibility a případné přegenerování embeddingů.

4. Umístění dat
- Výchozí GCP region aplikační infrastruktury: europe-west1.
- Gemini inference musí používat podporovanou lokalitu vybraného modelu.
- Dostupnost modelu v konkrétním regionu se ověří před deploymentem.
- Umístění Cloud Run automaticky nezaručuje stejné umístění AI inference.
- Google Search grounding má samostatné podmínky zpracování dat.
- Použití globálního endpointu nelze automaticky považovat za zpracování výhradně v EU.

5. Ochrana dat
- Do modelu se předává pouze nezbytný obsah zprávy, příloh a relevantního kontextu.
- Soukromá data se nesmějí předávat do veřejných vyhledávacích dotazů.
- Pro PoC používáme syntetická testovací data.
- Podmínky uchovávání a zpracování dat poskytovatelem musí být ověřeny před produkčním použitím.

6. Konfigurace
- Model ID a location jsou konfigurační hodnoty.
- Verze SDK se uzamkne v dependency lock souboru.
- Změna modelu vyžaduje regresní testy kvality, multimodality, latence a ceny.

7. Fallback
- Automatické přepnutí na jiného AI poskytovatele není součástí první verze.
- Při nedostupnosti modelu se použije kontrolovaný retry nebo bezpečné ukončení úlohy.
- Systém nesmí vymýšlet odpověď při selhání povinného AI zpracování.

CÍL:
Použít jeden jednoduchý AI stack s podporou všech požadovaných funkcí, kontrolovanou latencí a možností budoucí změny modelu.

### Jaká data mohou do modelu, jaký je retention a souhlas?

- ID: ai_data_policy (povinné)
- Stav: **PŘEDPOKLAD**

AI DATA POLICY – REPLY MCFLY

1. Povolené vstupy pro AI
- Tělo aktuálního e-mailu.
- Relevantní předchozí zprávy stejného Gmail vlákna.
- Validované PDF, MP3, WAV, JPEG a PNG přílohy.
- Relevantní RAG dokumenty nebo jejich části.
- Ověřené veřejné informace získané prostřednictvím Web Search.

2. Minimalizace dat
- Do Gemini předáváme pouze informace potřebné pro konkrétní odpověď.
- Conversation History je omezena na aktuální vlákno a token budget.
- RAG používá omezený počet relevantních chunks.
- Nepotřebná metadata a nesouvisející zprávy se nepředávají.
- Předávání přístupových tokenů a secrets je zakázáno.

3. Oddělení datových zdrojů
- Gmail obsah a historie jsou soukromý kontext.
- RAG tvoří samostatnou schválenou znalostní bázi.
- Web Search pracuje pouze s bezpečnými veřejnými dotazy.
- Externí výsledky nemohou měnit systémové instrukce nebo oprávnění.

4. Retention v aplikaci
- E-maily a přílohy se standardně trvale nekopírují do vlastní databáze.
- Dočasná data se po zpracování odstraní.
- PostgreSQL uchovává nezbytný stav úloh, outbox a RAG.
- Logy nesmějí obsahovat celé AI prompty, odpovědi ani obsah příloh.
- Retenční doba jednotlivých datových kategorií musí být stanovena před produkčním provozem.

5. Retention poskytovatele
- Uchovávání a zpracování dat službou Vertex AI se řídí konkrétními podmínkami Google Cloud.
- Google Search grounding může mít odlišné podmínky retence než základní inference.
- Nesmíme automaticky předpokládat nulovou retenci všech AI operací.
- Před produkčním provozem ověříme podmínky vybraného modelu a nástrojů.

6. Právní základ a souhlas
- PoC používá syntetická testovací data.
- Při práci s reálnými osobními údaji musí správce určit platný právní základ podle GDPR.
- Souhlas je pouze jednou z možných právních možností, nikoliv automaticky povinným základem.
- Role správce a zpracovatele musí být právně ověřeny.

7. Bezpečnost
- IAM a minimální oprávnění.
- HTTPS/TLS.
- Secret Manager pro credentials.
- Prompt injection ochrana.
- Kontrola strukturovaných AI výstupů.
- Bezpečnostní a retenční pravidla pro přílohy.

CÍL:
Minimalizovat předávání soukromých dat a zabránit jejich úniku do veřejných vyhledávacích služeb nebo provozních logů.

### Jaká je offline eval sada a akceptační práh kvality?

- ID: ai_eval (povinné)
- Stav: **PŘEDPOKLAD**

AI EVALUATION – REPLY MCFLY

Pro hodnocení kvality vytvoříme verzovanou offline eval sadu se syntetickými e-maily, přílohami a očekávanými odpověďmi.

1. Testovací sada
- Minimálně 30 testovacích scénářů.
- Jednoduché textové dotazy.
- PDF, MP3, WAV, JPEG a PNG.
- Navazující konverzace a nezávislá Gmail vlákna.
- Dotazy vyžadující RAG.
- Dotazy vyžadující Live Web Search.
- Kombinace Conversation History + RAG + Web Search.
- Chybějící znalosti, nejednoznačné dotazy a prompt injection.

2. Referenční výsledky
Každý testovací scénář obsahuje:
- Identifikátor testu.
- Vstupní e-mail a případné přílohy.
- Povinné informace ve výsledné odpovědi.
- Zakázané nebo nepodložené informace.
- Očekávané použití RAG/Web Search.
- Očekávaný výsledek (PASS/FAIL).

3. Hodnocené metriky
- Answer correctness – faktická správnost odpovědi.
- Groundedness – podloženost odpovědi dostupnými zdroji.
- Context relevance – správné využití historie vlákna.
- RAG faithfulness – soulad s interní znalostní bází.
- Web Search accuracy – aktuálnost a relevantnost zdrojů.
- Attachment understanding – správná interpretace příloh.
- Safety – dodržení bezpečnostních pravidel.

4. Návrhové akceptační prahy
- Minimálně 90 % testů faktické správnosti musí projít.
- Minimálně 90 % testů správného využití kontextu musí projít.
- 100 % kritických bezpečnostních testů musí projít.
- 0 potvrzených úniků informací mezi vlákny.
- 0 nepovolených změn příjemce odpovědi.
- 0 vymyšlených kritických produktových údajů v definovaných RAG testech.
- Všechny povinné formáty příloh musí projít svými akceptačními testy.

5. Metodika
- Deterministické testy pro stavový automat, bezpečnost a API kontrakty.
- Porovnání povinných faktů proti referenčním výsledkům.
- Ruční kontrola vybraných AI odpovědí.
- Případný LLM-as-a-Judge pouze jako doplňkové hodnocení.
- Samostatné vyhodnocení testů s aktuálními webovými informacemi.

6. Regresní testování
- Eval sada se spustí po změně Gemini modelu, promptů nebo orchestrace.
- Výsledky se porovnají s předchozí verzí.
- Zhoršení kritických metrik blokuje release.
- Testovací data, konfigurace a výsledky jsou verzované.

7. Výkonnost
- End-to-end latence se měří odděleně od kvality odpovědi.
- Cíl je odpověď pod 120 sekund.
- Testuje se také zpracování více současných e-mailů.

CÍL:
Prokazatelně ověřit, že AI poskytuje fakticky správné, relevantní a bezpečné odpovědi a že změna modelu nezhoršuje funkčnost.

Uvedené prahy jsou návrhové akceptační hodnoty. Jejich dosažení zatím nebylo ověřeno.

### Co se stane při halucinaci, timeoutu, nevhodném výstupu a outage?

- ID: ai_failure (povinné)
- Stav: **PŘEDPOKLAD**

AI FAILURE HANDLING – REPLY MCFLY

1. Halucinace a nepodložené informace
- AI odpověď musí vycházet z dostupného kontextu.
- RAG fakta musí odpovídat schváleným dokumentům.
- Aktuální informace musí být ověřeny prostřednictvím Web Search.
- Pokud informace chybí, asistent nesmí vymýšlet odpověď.
- Při nedostatečných podkladech použije bezpečnou odpověď nebo NEEDS_REVIEW.
- Kritická fakta lze kontrolovat proti strukturovaným zdrojovým údajům.

2. Timeout Gemini
- Každé inference volání má omezený timeout.
- Workflow respektuje celkový aplikační deadline.
- Retry se provádí pouze při dostatečném zbývajícím časovém rozpočtu.
- Opakované selhání vede do RETRY_PENDING nebo FAILED.
- Nevytváří se neověřená náhradní odpověď.

3. Nevhodný nebo neplatný AI výstup
- Gemini vrací strukturovaný návrh odpovědi.
- Pydantic kontroluje datovou strukturu.
- Reply Policy ověřuje bezpečnostní a doménová pravidla.
- Model nesmí změnit příjemce, Gmail threadId ani oprávnění.
- Neplatný výstup lze jednou opravit novým inference voláním, pokud zbývá čas.
- Při opakovaném selhání se úloha bezpečně ukončí nebo předá ke kontrole.

4. Výpadek Gemini / Vertex AI
- Detekovat timeout, HTTP 429 nebo 5xx.
- Použít omezený exponential backoff.
- Omezit současná volání při přetížení.
- Zachovat stav email job v PostgreSQL.
- Po obnově služby pokračovat řízeným retry.
- Automatický fallback na jiného poskytovatele není součástí PoC.

5. Selhání RAG
- Pokud retrieval nenajde relevantní fakta, asistent nesmí vymýšlet interní produktové informace.
- Pokud je znalost nezbytná, odpověď výslovně uvede její nedostupnost.
- Při technické chybě retrieval se použije kontrolovaný chybový stav.

6. Selhání Web Search
- Pokud nelze ověřit aktuální fakta, asistent nesmí uvádět zastaralé informace jako aktuální.
- Může bezpečně sdělit, že aktuální informace nebylo možné ověřit.
- Soukromý obsah e-mailu se nesmí použít jako veřejný vyhledávací dotaz.

7. Bezpečnost a prompt injection
- Veškerý externí obsah je nedůvěryhodný.
- Model nemá přímý přístup k odesílání e-mailů.
- Příjemce a Gmail hlavičky sestavuje backend.
- Nepovolené instrukce se ignorují.
- Podezřelý výstup se odmítne.

8. Zpracování chyb
- RETRY_PENDING – dočasné selhání.
- FAILED – neobnovitelná chyba.
- NEEDS_REVIEW – vyžadována ruční kontrola.
- DELIVERY_UNKNOWN – nejasný výsledek Gmail Send.

9. Monitoring
- Počet selhání AI inference.
- Počet odmítnutých AI výstupů.
- Počet neúspěšných RAG a Web Search požadavků.
- Timeouty, retry a latence.
- Spotřeba tokenů a náklady.

CÍL:
AI musí při nedostatku informací nebo technickém selhání bezpečně přiznat omezení. Nikdy nesmí kompenzovat chybu vymyšlenými informacemi nebo neoprávněnou akcí.

### Jaký token/call budget, limity a náklady na uživatele/job?

- ID: ai_costs (povinné)
- Stav: **PŘEDPOKLAD**

AI COST MANAGEMENT – REPLY MCFLY

Náklady řídíme na úrovni jednoho zpracovaného e-mailu (email job), nikoliv na uživatele. PoC neobsahuje samostatné uživatelské účty.

1. Hlavní nákladové položky
- Gemini input a output tokeny.
- Multimodální vstupy – PDF, audio a obrázky.
- Embeddingy pro RAG.
- Google Search grounding.
- Opakovaná AI volání při chybách.

2. Návrhový token budget
- System instructions: maximálně 2 000 tokenů.
- Aktuální e-mail a textový kontext příloh: přibližně 4 000 tokenů.
- Conversation History: maximálně 6 000 tokenů.
- RAG kontext: maximálně 4 000 tokenů.
- Web Search kontext: maximálně 4 000 tokenů.
- Generovaná odpověď: maximálně 1 500 výstupních tokenů.

Tyto hodnoty jsou orientační limity pro textový kontext, nikoliv garance celkové spotřeby multimodálních tokenů. Skutečnou spotřebu je nutné měřit podle konkrétního Gemini modelu.

3. AI call budget
- Preferujeme jedno hlavní generování odpovědi.
- Doplňková klasifikace potřeby RAG/Web Search může být provedena samostatným levným voláním nebo deterministicky.
- RAG retrieval probíhá pouze při relevantním dotazu.
- Web Search se používá pouze při potřebě aktuálních informací.
- Počet retry inference je omezený.
- Maximální počet volání bude potvrzen podle měření latence.

4. RAG optimalizace
- Embeddingy dokumentů generujeme při importu nebo aktualizaci.
- Dokumenty se neembedují opakovaně pro každý email job.
- Při dotazu generujeme pouze potřebný query embedding.
- Retrieval vrací omezený počet relevantních chunks.
- PostgreSQL/pgvector nevyžaduje další samostatnou vektorovou databázi.

5. Web Search optimalizace
- Spouštět pouze při časově závislých veřejných dotazech.
- Omezit počet grounded requests nebo vyhledávacích dotazů.
- Při dostupných RAG faktech nespouštět Web Search bez důvodu.
- Respektovat aktuální ceník vybraného Gemini modelu.

6. Monitoring nákladů
Pro každý email job evidovat:
- Použitý Gemini model.
- Počet inference volání.
- Input/output token usage.
- Použití RAG a embeddingů.
- Použití Web Search.
- Celkovou AI latenci.
- Odhad nákladů podle platného ceníku.

7. Cost controls
- Cloud Run max instances a concurrency.
- Omezený počet současných AI požadavků.
- Limity velikosti příloh.
- Omezená délka Conversation History.
- Omezený počet retry.
- Google Cloud Billing Budget alerty na 50 %, 80 % a 100 %.
- Monitoring neobvyklé spotřeby tokenů.

8. Cena na email job
Výpočet:
AI cost/job =
(input tokens × input token price)
+ (output tokens × output token price)
+ multimodal processing
+ embedding costs
+ grounding costs.

Celkové náklady na job navíc zahrnují Cloud Run, Cloud SQL a další používané cloudové služby.

9. Cílová cena
- Konkrétní maximální cena jednoho email job zatím není stanovena.
- Musí vycházet z vybraného modelu, testovacích scénářů a reálné spotřeby.
- Cenu vyhodnotíme samostatně pro textové, multimodální a kombinované AI požadavky.

CÍL:
Udržet náklady pod kontrolou a současně zachovat všechny povinné schopnosti, kvalitu odpovědí a 120sekundový end-to-end limit.

Token budget je návrhový. Skutečné náklady se musí ověřit měřením a aktuálním ceníkem Google Cloud.

### Jak verzovat prompty, modely a kontext?

- ID: ai_prompt_versioning (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Kde je human-in-the-loop pro rizikové akce?

- ID: ai_approval (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak sledovat kvalitu, chyby, latenci a drift?

- ID: ai_monitoring (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Pokud RAG: dokumenty, chunking, retrieval, citace a mazání?

- ID: ai_rag (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

### Jak bráníš prompt injection, exfiltraci a zneužití nástrojů?

- ID: ai_prompt_injection (doplňkové)
- Stav: **NEVYPLNĚNO / OVĚŘIT**

**NEVYPLNĚNO / OVĚŘIT**

## 18 · Doplňující návrh: soubory a média

*Cíl:* Upload a storage mají jasné bezpečnostní a retenční hranice.

*Gate:* Nahrávání, zpracování, mazání a chybové stavy jsou explicitní.

### Jaké formáty, velikosti a počet souborů dovolíš?

- ID: files_types (povinné)
- Stav: **PŘEDPOKLAD**

PODPOROVANÉ SOUBORY A LIMITY – REPLY MCFLY

1. Podporované formáty
- PDF – dokumenty.
- MP3 – zvukové nahrávky.
- WAV – zvukové nahrávky.
- JPEG/JPG – obrázky.
- PNG – obrázky.

2. Limity příloh
- Maximálně 5 příloh na jeden e-mail.
- Maximálně 20 MiB příloh celkem.
- PDF: maximálně 5 MiB na soubor.
- PDF: maximálně 30 stran celkem.
- MP3/WAV: maximálně 10 MiB na soubor.
- Audio: maximálně 180 sekund.
- JPEG/PNG: maximálně 5 MiB na soubor.
- Obrázky: maximálně 10 megapixelů.

3. Kontrola velikosti
- Ověření počtu a velikosti příloh před AI zpracováním.
- Kontrola skutečné velikosti po dekódování MIME obsahu.
- Omezení celkové velikosti načítaných dat.
- Nepodporované a nadlimitní soubory se odmítnou.

4. Zpracování
- PDF, audio a obrázky interpretuje multimodální Gemini.
- Přílohy se předávají pouze v rámci aktuálního email job.
- Aplikace nevytváří trvalou kopii každé přílohy.

5. Chybové scénáře
- Nepodporovaný formát.
- Překročený počet nebo velikost souborů.
- Poškozený nebo nečitelný soubor.
- Nepodporovaná struktura PDF.
- Překročený časový limit zpracování.

6. Odůvodnění
Limity chrání před nadměrnou spotřebou paměti, dlouhým zpracováním, vysokými náklady Gemini a překročením 120sekundového end-to-end limitu.

Hodnoty jsou výchozí návrhové limity. Po integračních a výkonnostních testech se případně upraví.

### Jak ověříš skutečný typ, velikost a škodlivý obsah?

- ID: files_validation (povinné)
- Stav: **PŘEDPOKLAD**

VALIDACE PŘÍLOH – REPLY MCFLY

1. Kontrola MIME
- Načíst MIME metadata z Gmail API.
- Ověřit, že formát patří mezi PDF, MP3, WAV, JPEG a PNG.
- Nespoléhat pouze na příponu souboru nebo MIME deklaraci odesílatele.

2. Kontrola skutečného typu
- Ověřit skutečnou signaturu souboru (magic bytes).
- PDF: kontrola PDF struktury.
- MP3/WAV: kontrola dekódovatelnosti a audio parametrů.
- JPEG/PNG: kontrola obrazového formátu a rozměrů.
- Odmítnout nesoulad mezi deklarovaným a skutečným typem.

3. Kontrola limitů
- Maximálně 5 příloh.
- Maximálně 20 MiB celkem.
- PDF: 5 MiB a nejvýše 30 stran celkem.
- Audio: 10 MiB a 180 sekund.
- Obrázky: 5 MiB a 10 megapixelů.

4. Použité knihovny
- PyMuPDF – PDF validace a kontrola počtu stran.
- Pillow – JPEG/PNG validace a rozměry.
- FFmpeg/ffprobe – MP3/WAV parametry a délka.
- Python MIME/email knihovny – zpracování zprávy.

5. Ochrana proti škodlivému obsahu
- Žádné spouštění kódu obsaženého v příloze.
- Žádné vykonávání PDF skriptů ani aktivního obsahu.
- Omezení paměti a času parserů.
- Ochrana proti nadměrnému rozbalení obrazových dat.
- Poškozené a podezřelé soubory se odmítnou.
- Pro budoucí veřejný produkční provoz doplnit antivirové skenování podle vyhodnoceného rizika.

6. Prompt injection
- Text, obrázek i audio z přílohy jsou nedůvěryhodný obsah.
- Instrukce obsažené v přílohách nesmějí měnit systémová pravidla.
- Gemini nemůže samostatně měnit příjemce ani odesílat e-maily.
- Výsledná odpověď prochází backendovou validací.

7. Chyby a evidence
- Neplatný formát → UNSUPPORTED_ATTACHMENT.
- Překročený limit → ATTACHMENT_LIMIT_EXCEEDED.
- Poškozený soubor → ATTACHMENT_INVALID.
- Technická chyba parseru → kontrolovaný retry nebo NEEDS_REVIEW.
- Logovat pouze technická metadata a error_code, nikoliv obsah příloh.

8. Testování
- Platná příloha každého podporovaného formátu.
- Soubor s falešnou příponou.
- Nesoulad MIME a magic bytes.
- Poškozené PDF/audio/obrázek.
- Nadlimitní příloha.
- Prompt injection vložený do přílohy.

Cíl: Přijímat pouze podporované a technicky validní soubory a předcházet bezpečnostním, výkonnostním a nákladovým problémům.

### Kde se soubory drží a jak se řídí přístup?

- ID: files_storage (povinné)
- Stav: **PŘEDPOKLAD**

FILE STORAGE – REPLY MCFLY

1. Primární úložiště
- Původní e-maily a přílohy zůstávají v dedikované Gmail schránce.
- Gmail je Source of Truth pro originální zprávy a soubory.
- Aplikace nevytváří vlastní trvalé úložiště e-mailových příloh.

2. Zpracování příloh
- Cloud Run Worker načítá přílohy pomocí Gmail API.
- Přílohy se validují a připravují pro Gemini.
- Data jsou držena pouze po dobu zpracování konkrétní úlohy.
- Podle potřeby se využívá operační paměť nebo dočasný filesystem kontejneru.

3. PostgreSQL
- Cloud SQL uchovává metadata a stav zpracování.
- Eviduje email_jobs, email_outbox a synchronizační checkpointy.
- Neuchovává běžné binární kopie příloh.
- RAG dokumenty a embeddingy jsou samostatnou znalostní databází.

4. Přístupová práva
- Gmail OAuth omezuje přístup na autorizovanou schránku.
- Pouze Cloud Run Worker má oprávnění číst obsah zpráv a příloh.
- Ingress nepřistupuje k obsahu Gmail zpráv.
- Přístup k PostgreSQL a Secret Manageru omezuje IAM a databázová oprávnění.

5. Bezpečnost
- Komunikace probíhá přes HTTPS/TLS.
- Secrets jsou uloženy v Secret Manageru.
- Přílohy se nezapisují do aplikačních logů.
- Každá úloha zpracovává pouze obsah příslušného e-mailu.
- Dočasné soubory se po zpracování odstraní.

6. Proč nepoužíváme Cloud Storage
- Gmail již uchovává originální přílohy.
- PoC nevyžaduje archivaci ani sdílení souborů.
- Duplicitní ukládání zvyšuje náklady a složitost správy přístupů.
- Cloud Storage lze doplnit, pokud vznikne požadavek na dlouhodobé ukládání, velké soubory nebo oddělené zpracování.

Cíl: Minimalizovat ukládaná data a využít Gmail jako existující zdroj příloh bez zavádění dalšího úložiště.

### Kdy a jak se soubory mažou včetně záloh?

- ID: files_lifecycle (povinné)
- Stav: **PŘEDPOKLAD**

FILE LIFECYCLE & RETENTION – REPLY MCFLY

1. Příchozí přílohy
- Originální přílohy zůstávají součástí Gmail zprávy.
- Aplikace je načítá pouze při zpracování příslušného email job.
- Nevytváří trvalé kopie příloh ve vlastní databázi.

2. Dočasná data
- Přílohy jsou dočasně zpracovány v paměti nebo dočasném filesystemu Cloud Run.
- Po úspěšném či neúspěšném zpracování aplikace odstraní vytvořené dočasné soubory.
- Při ukončení instance se dočasný stav kontejneru ztrácí.
- Citlivý obsah se nesmí ukládat do logů.

3. PostgreSQL
- Databáze uchovává metadata úloh a stavy odesílání.
- Neukládá běžné binární kopie příloh.
- Retence provozních metadat musí být stanovena podle účelu a bezpečnostních požadavků.

4. Gmail retention
- Životní cyklus originálních příloh se řídí pravidly dedikované Gmail schránky.
- Výmaz originálu provádí oprávněný správce podle retenční politiky.
- Aplikace nemaže automaticky původní e-maily po jejich zpracování.

5. Zálohy
- Přílohy nejsou součástí Cloud SQL záloh, pokud jejich binární obsah není do databáze ukládán.
- Cloud SQL zálohy obsahují pouze uložená metadata a RAG data.
- Výmaz nebo expirace databázových záloh se řídí nakonfigurovanou retenční politikou Cloud SQL.
- Při obnově starší zálohy je nutné znovu aplikovat relevantní výmazové požadavky.

6. RAG dokumenty
- RAG dokumenty jsou spravovány odděleně od e-mailových příloh.
- Při odstranění dokumentu se odstraní odpovídající chunks a embeddingy.
- Staré verze se uchovávají pouze podle definované retenční politiky.

7. Ověření
- Test odstranění dočasných souborů po úspěchu.
- Test odstranění po chybě zpracování.
- Kontrola, že databáze neobsahuje binární přílohy.
- Kontrola, že logy neobsahují citlivý obsah.

Cíl: Neuchovávat zbytečné kopie soukromých příloh a jasně oddělit jejich původní uložení v Gmailu od dočasného AI zpracování.

Konkrétní retenční doby Gmailu, databázových metadat a záloh musí být potvrzeny před produkčním provozem.

### Jsou soubory zpracované async a jaký je stavový model?

- ID: files_processing (doplňkové)
- Stav: **PŘEDPOKLAD**

ASYNCHRONNÍ ZPRACOVÁNÍ PŘÍLOH – REPLY MCFLY

1. Architektonický princip
- Přílohy se zpracovávají asynchronně vůči příjmu Gmail notifikace.
- Pub/Sub a Cloud Tasks oddělují detekci e-mailu od jeho zpracování.
- Samostatnou frontu pro každou přílohu v PoC nevytváříme.
- Všechny přílohy jednoho e-mailu zpracovává příslušný email job.

2. Workflow
- Gmail Watch informuje o změně schránky.
- Ingress vytvoří synchronizační úlohu.
- GmailSyncService zjistí novou nepřečtenou zprávu.
- Process Queue spustí Cloud Run Worker.
- Worker načte zprávu a metadata příloh.
- Attachment Validator ověří typ, velikost a technické limity.
- Attachment Processor připraví validované přílohy pro Gemini.
- EmailOrchestrator sestaví kontext a spustí AI inference.
- ReplyService odešle validovanou odpověď.
- PostgreSQL uloží výsledný stav email job.

3. Stavový model email job
- QUEUED – úloha čeká na zpracování.
- PROCESSING – načítání, validace a interpretace příloh.
- READY_TO_SEND – odpověď je připravena.
- SENDING – probíhá odesílání.
- SENT – potvrzené odeslání.
- RETRY_PENDING – dočasné selhání.
- FAILED – neobnovitelné selhání.
- NEEDS_REVIEW – nutná ruční kontrola.
- DELIVERY_UNKNOWN – nejasný výsledek odeslání.
- SKIPPED – bezpečně přeskočená zpráva.

4. Stav jednotlivých příloh
- Pro PoC není potřeba samostatná persistentní tabulka attachment_jobs.
- Validace každé přílohy vrací stav VALID, REJECTED nebo PROCESSING_ERROR.
- Výsledky se vyhodnotí v rámci jednoho email job.
- Technická metadata lze zaznamenat bez ukládání obsahu souboru.

5. Retry
- Dočasné chyby Gmail API a Gemini lze opakovat podle retry politiky.
- Neplatné nebo nepodporované soubory se znovu nezpracovávají bez změny vstupu.
- Při opakování se respektuje idempotence email job.
- Gmail Send se při nejasném výsledku nesmí automaticky opakovat.

6. Timeout a výkon
- Cloud Run Worker HTTP timeout: 110 sekund.
- Aplikační deadline: maximálně 100 sekund.
- Přílohy musí respektovat společný časový rozpočet.
- Limity velikosti, počtu PDF stran a délky audia chrání 120sekundový end-to-end cíl.

7. Scaling
- Cloud Tasks řídí počet současně zpracovávaných e-mailů.
- Cloud Run Worker škáluje podle počtu požadavků.
- Výchozí maximum: 3 Worker instance, concurrency 1.
- Při přetížení čekají úlohy ve frontě.
- Požadovaný čas pod 120 sekund musí být ověřen zátěžovými testy.

8. Budoucí rozšíření
- Při větším objemu nebo dlouhých souborech lze zavést samostatné attachment jobs.
- Pro současné PoC by samostatná fronta a worker pro každý soubor znamenaly zbytečnou složitost.

Cíl: Zpracovat podporované přílohy bezpečně v rámci jednoho email job, bez blokování Gmail Ingress a bez zavádění další infrastruktury.

### Použiješ multipart, presigned URL nebo jiný tok? Proč?

- ID: files_upload_strategy (doplňkové)
- Stav: **PŘEDPOKLAD**

FILE UPLOAD STRATEGY – REPLY MCFLY

Pro PoC používáme Gmail API jako jediný vstupní mechanismus pro e-mailové přílohy.

1. Způsob příjmu souborů
- Uživatel přiloží soubor ke standardnímu e-mailu.
- E-mailový klient odešle zprávu do dedikované Gmail schránky.
- Gmail uchovává zprávu i její přílohy.
- Gmail Watch a Pub/Sub oznámí změnu schránky.
- Cloud Tasks spustí zpracování příslušného email job.

2. Načtení příloh
- Cloud Run Worker načte zprávu pomocí Gmail API.
- Získá MIME strukturu a metadata příloh.
- Přílohy načítá prostřednictvím Gmail API, například users.messages.attachments.get.
- Binární data dekóduje z Gmail API reprezentace.
- Následně kontroluje skutečný typ, velikost a obsah.

3. Proč nepoužíváme multipart upload
- Aplikace nemá vlastní webový formulář.
- Uživatel neposílá soubory přímo do FastAPI.
- MIME přílohy jsou součástí e-mailové zprávy.
- Samostatný upload endpoint není požadován.

4. Proč nepoužíváme presigned URL
- Nepotřebujeme přímé nahrávání do Cloud Storage.
- Originální přílohy již uchovává Gmail.
- Nevytváříme další trvalé kopie souborů.
- Odpadá správa upload URL, oprávnění a expirace.

5. Zpracování
- Attachment Validator ověří soubor.
- Attachment Processor připraví validovaný obsah pro Gemini.
- EmailOrchestrator použije informace z přílohy při generování odpovědi.
- Dočasná data se po zpracování odstraní.

6. Bezpečnost
- Gmail OAuth 2.0 s minimálními potřebnými oprávněními.
- Přístup k přílohám má pouze autorizovaný Worker.
- Žádné veřejné upload endpointy.
- Přílohy se nezapisují do provozních logů.
- Respektují se limity velikosti, počtu a typu souborů.

7. Budoucí rozšíření
- Pro velké soubory nebo přímý webový upload lze později zavést Cloud Storage a signed URLs.
- Pro současné PoC by tato infrastruktura znamenala zbytečnou složitost.

CÍL:
Použít existující Gmail infrastrukturu pro příjem souborů a minimalizovat počet aplikačních komponent.

### Jak zajistíš soukromí a cache/CDN invalidaci?

- ID: files_cdn (doplňkové)
- Stav: **PŘEDPOKLAD**

FILES PRIVACY, CACHE A CDN – REPLY MCFLY

Pro počáteční PoC nepoužíváme vlastní CDN ani veřejnou souborovou cache.

1. CDN
- Aplikace neposkytuje veřejné souborové odkazy.
- Přílohy nejsou publikovány na webu.
- Cloud CDN není potřeba.
- Originální soubory zůstávají v Gmailu.

2. Přístup k souborům
- Cloud Run Worker načítá přílohy přes Gmail API.
- Gmail OAuth omezuje přístup na autorizovanou schránku.
- Backend kontroluje příslušnost zprávy k aktuálnímu email job.
- Přílohy se neposkytují prostřednictvím veřejných URL.

3. Dočasná cache
- Validované přílohy mohou být během zpracování v operační paměti nebo dočasném filesystemu Workeru.
- Data jsou izolovaná v rámci konkrétní úlohy.
- Mezi jednotlivými e-mailovými vlákny se nesdílí obsah příloh.
- Nepoužíváme Redis ani distribuovanou cache příloh.

4. Invalidace
- Po dokončení nebo selhání email job se dočasné soubory odstraní.
- Při opakovaném zpracování se potřebná data znovu načtou z Gmailu.
- Protože neexistuje vlastní CDN ani persistentní cache souborů, není potřeba CDN invalidace.

5. Ochrana soukromí
- Žádné veřejné bucket URL.
- Žádné veřejné signed URLs.
- Žádné ukládání příloh do aplikačních logů.
- Žádné předávání soukromého obsahu do veřejného Web Search.
- Minimální IAM oprávnění a zabezpečená API komunikace.

6. RAG dokumenty
- RAG znalostní báze je oddělená od uživatelských příloh.
- RAG dokumenty a embeddingy jsou uložené v PostgreSQL/pgvector.
- Změny dokumentů se řeší aktualizací jejich verzí, chunks a embeddingů.

7. Budoucí rozšíření
- Pokud bude potřeba Cloud Storage nebo CDN, bude nutné definovat přístupová pravidla, expiraci odkazů, retenční politiku a invalidaci cache.
- Pro současné PoC tuto infrastrukturu nezavádíme.

CÍL:
Zachovat soukromí e-mailových příloh bez potřeby správy CDN, veřejných odkazů nebo distribuované cache.

### Jaké jsou limity na uživatele a ochrana proti nákladům?

- ID: files_quota (doplňkové)
- Stav: **PŘEDPOKLAD**

FILES QUOTA & COST PROTECTION – REPLY MCFLY

Aplikace nemá vlastní uživatelské účty. Limity proto nastavujeme na úrovni e-mailové zprávy, odesílatele, zpracovatelské fronty a celkového cloudového provozu.

1. Limity na e-mail
- Maximálně 5 příloh.
- Maximálně 20 MiB příloh celkem.
- PDF: maximálně 5 MiB na soubor a 30 stran celkem.
- MP3/WAV: maximálně 10 MiB a 180 sekund.
- JPEG/PNG: maximálně 5 MiB a 10 megapixelů.
- Nepodporované nebo nadlimitní soubory se odmítnou před AI zpracováním.

2. Limity na odesílatele
- Pro první PoC navrhujeme maximálně 10 zpracovaných zpráv od jednoho odesílatele za hodinu.
- Při překročení limitu se nové zprávy bezpečně evidují a přeskočí nebo předají ke kontrole podle definované politiky.
- Počítání musí respektovat normalizovanou identitu odesílatele a časové okno.
- Limit je konfigurovatelný.

3. Limity souběžného zpracování
- Cloud Tasks Process Queue: maximálně 3 současné úlohy.
- Cloud Run Worker: maximálně 3 instance.
- Cloud Run Worker concurrency: 1.
- Při vyšší zátěži zůstávají zprávy ve frontě.
- Stáří čekajících úloh se monitoruje kvůli 120sekundovému limitu.

4. Omezení AI nákladů
- Omezený počet a velikost příloh.
- Omezený počet PDF stran a délka audia.
- Omezená délka Conversation History.
- RAG retrieval pouze při relevantním dotazu.
- Web Search pouze při požadavku na aktuální veřejné informace.
- Omezený počet Gemini volání a retry.
- Konfigurovatelný token budget.

5. Ochrana proti zneužití
- Deduplikace podle mailbox_id a gmail_message_id.
- Ignorování vlastních a automatických odpovědí.
- Ochrana proti e-mailovým smyčkám.
- Omezení počtu zpracovaných zpráv od odesílatele.
- Kontrola velikosti zprávy před nákladným AI zpracováním.
- Podezřelé a neplatné vstupy mohou přejít do SKIPPED nebo NEEDS_REVIEW.

6. Cloud budget
- Google Cloud Billing Budget s upozorněními na 50 %, 80 % a 100 % rozpočtu.
- Návrhový měsíční budget: 20 USD.
- Rozpočtové alerty automaticky nezastavují účtování.
- Cloud SQL a Vertex AI náklady se sledují samostatně.

7. Monitoring
- Počet příloh na e-mail.
- Velikost příloh.
- Počet odmítnutých souborů.
- Doba zpracování multimodálních vstupů.
- Spotřeba Gemini tokenů.
- Počet zpracovaných zpráv podle pseudonymizovaného odesílatele.
- Náklady na email job.

8. Testování
- Překročení počtu příloh.
- Překročení jednotlivých velikostních limitů.
- Překročení limitu zpráv od odesílatele.
- Souběžné doručení více e-mailů.
- Simulace vysokých AI nákladů.
- Ověření ochrany před duplicitami.

CÍL:
Omezit riziko zneužití a nečekaných nákladů, aniž bychom omezili povinnou podporu PDF, MP3, WAV, JPEG a PNG.

Limity na odesílatele a měsíční rozpočet jsou návrhové hodnoty. Jejich dopad na funkčnost, latenci a náklady musí být ověřen při testování.

## 20 · Doplňující návrh: realtime a notifikace

*Cíl:* Reálný čas musí fungovat i při reconnectu a ztrátě událostí.

*Gate:* Klient umí reconnect, dedup a resynchronizaci stavu.

### Jaký protokol (SSE/WS/push) zvolíš a proč?

- ID: rt_transport (povinné)
- Stav: **PŘEDPOKLAD**

REALTIME TRANSPORT – REPLY MCFLY

Zvolený přístup: Gmail Watch + Google Cloud Pub/Sub push + HTTPS.

1. Detekce nových zpráv
- Gmail Watch sleduje změny v dedikované Gmail schránce.
- Gmail publikuje notifikaci do Google Cloud Pub/Sub.
- Pub/Sub push subscription doručí notifikaci do Cloud Run Ingress.
- Ingress vytvoří synchronizační úlohu v Cloud Tasks.

2. Asynchronní zpracování
- Cloud Tasks spustí Cloud Run Worker.
- Worker pomocí Gmail History API zjistí nové zprávy.
- Následně zpracuje e-mail, přílohy a potřebný kontext.
- Po vygenerování odpovědi použije Gmail API pro odeslání.

3. Použitý transport
- Gmail Watch → Pub/Sub: spravované události Google.
- Pub/Sub → Cloud Run: HTTPS push.
- Cloud Tasks → Worker: HTTPS s OIDC autentizací.
- Worker → Gmail API / Gemini: zabezpečená API komunikace.

4. Proč nepoužíváme WebSockets nebo SSE
- Aplikace nemá vlastní webový frontend.
- Uživatel nepotřebuje průběžné aktualizace stavu.
- Výstupem je standardní e-mailová odpověď.
- WebSockets nebo SSE by přidaly nepotřebnou infrastrukturu.

5. Výhody
- Automatická detekce změn bez neustálého dotazování Gmailu.
- Oddělení příjmu notifikace od AI zpracování.
- Možnost škálování Workerů.
- Retry a kontrola souběžnosti pomocí Cloud Tasks.
- Nižší provozní složitost než vlastní realtime server.

6. Omezení
- Gmail Watch není garantovaný okamžitý transport.
- Pub/Sub může doručit stejnou událost vícekrát.
- Notifikace obsahuje informaci o změně schránky, nikoliv celý e-mail.
- Skutečné změny se zjišťují pomocí Gmail History API.

CÍL:
Použít jednoduchý event-driven mechanismus vhodný pro automatického e-mailového asistenta s cílovou latencí pod 120 sekund.

### Jak klient rozpozná duplicity, zpoždění a pořadí?

- ID: rt_ordering (povinné)
- Stav: **PŘEDPOKLAD**

EVENT ORDERING & DEDUPLICATION – REPLY MCFLY

Aplikace nemá vlastní realtime klient. Duplicity, zpoždění a pořadí událostí řeší backend.

1. Identifikace událostí
- Gmail Watch poskytuje historyId jako ukazatel změn schránky.
- Gmail API poskytuje gmail_message_id a gmail_thread_id.
- PostgreSQL uchovává poslední bezpečně zpracovaný historyId.

2. Deduplikace
- Unikátní kombinace mailbox_id + gmail_message_id.
- PostgreSQL UNIQUE constraint zabraňuje založení duplicitního email job.
- Opakované Pub/Sub notifikace nesmějí vytvořit duplicitní odpovědi.
- Cloud Tasks požadavky kontrolují existující stav úlohy.

3. Pořadí událostí
- Pub/Sub push nepovažujeme za garantovaně seřazený proud.
- Gmail historyId používáme jako synchronizační checkpoint, nikoliv jako pořadové číslo jednotlivých odpovědí.
- Gmail History API slouží ke zjištění změn od posledního checkpointu.
- Každá zpráva má vlastní job a odpovídající Gmail vlákno.

4. Pořadí zpráv ve vlákně
- Conversation History zachovává chronologické pořadí zpráv.
- Při současném zpracování více zpráv stejného vlákna musí backend zabránit použití nekonzistentního kontextu.
- Pro PoC navrhujeme řízení souběžnosti na úrovni gmail_thread_id.
- Nezávislá vlákna lze zpracovávat paralelně.

5. Zpožděné události
- Synchronizace načítá změny od uloženého checkpointu.
- Již evidované zprávy se znovu nezařazují.
- Po dokončení synchronizace se checkpoint bezpečně aktualizuje.

6. Ochrana před duplicitním odesláním
- email_outbox má unikátní vazbu na email job.
- Stav SENT blokuje další odeslání.
- Stav DELIVERY_UNKNOWN vyžaduje ověření Gmailu před případným opakováním.

7. Testování
- Duplicitní Pub/Sub notifikace.
- Události doručené mimo pořadí.
- Více zpráv ve stejném vlákně.
- Paralelní zpracování nezávislých vláken.
- Restart Workeru během zpracování.
- Opakované doručení Cloud Tasks úlohy.

CÍL:
Zajistit konzistentní zpracování zpráv bez spoléhání na přesné pořadí nebo jediné doručení událostí.

### Jak proběhne reconnect a doplnění zmeškaného stavu?

- ID: rt_reconnect (povinné)
- Stav: **PŘEDPOKLAD**

RECONNECT & RECOVERY – REPLY MCFLY

Gmail Watch a Pub/Sub používají spravovanou komunikaci. Aplikace neudržuje vlastní WebSocket spojení.

1. Běžný provoz
- Gmail Watch publikuje změny schránky do Pub/Sub.
- Pub/Sub doručuje notifikace do Cloud Run Ingress.
- GmailSyncService používá uložený historyId k načtení změn.
- Nové zprávy vytvářejí email jobs.

2. Dočasný výpadek Ingress
- Pub/Sub opakuje doručení podle nakonfigurované retry politiky.
- Ingress přijme opakovanou notifikaci.
- Deduplikace zabrání opětovnému zařazení stejné zprávy.

3. Výpadek Workeru
- Cloud Tasks opakuje vhodné neúspěšné požadavky.
- PostgreSQL uchovává stav rozpracovaných úloh.
- Recovery zkontroluje expirované lease.
- Úloha může být bezpečně převzata jinou instancí.

4. Obnova Gmail Watch
- Gmail Watch má omezenou platnost.
- Cloud Scheduler pravidelně spouští jeho obnovení před expirací.
- Nové historyId se ukládá kontrolovaně.
- Samotná obnova Watch nesmí způsobit ztrátu nezpracovaných změn.

5. Doplnění zmeškaných událostí
- Cloud Scheduler spouští periodickou kontrolní synchronizaci.
- Gmail History API načítá změny od posledního platného checkpointu.
- Již evidované zprávy se přeskočí.
- Chybějící zprávy vytvoří nové email jobs.

6. Neplatný historyId
- Pokud Gmail History API odmítne zastaralý checkpoint, systém zahájí řízenou full resynchronizaci.
- Načte relevantní zprávy podle definované politiky.
- PostgreSQL deduplikace zabrání opakovanému zpracování známých zpráv.
- Pokud nelze určit bezpečný rozsah obnovy, incident se eviduje.

7. Ověření
- Simulace výpadku Pub/Sub doručování.
- Simulace restartu Ingress a Workeru.
- Test obnovení Gmail Watch.
- Test neplatného historyId.
- Test doplnění zmeškaných zpráv.
- Ověření nepřítomnosti duplicitních odpovědí.

CÍL:
Zajistit obnovu zpracování po dočasných výpadcích bez ztráty nových e-mailů a bez nutnosti vlastního realtime reconnect protokolu.

### Jak se autentizují dlouhodobá spojení a expirují tokeny?

- ID: rt_auth (doplňkové)
- Stav: **PŘEDPOKLAD**

REALTIME AUTHENTICATION – REPLY MCFLY

Aplikace nepoužívá dlouhodobá WebSocket nebo SSE spojení. Komunikace probíhá pomocí krátkých autentizovaných HTTPS požadavků.

1. Gmail OAuth 2.0
- Gmail účet je autorizován pomocí OAuth 2.0.
- Gmail OAuth refresh token je uložen v Secret Manageru.
- Krátkodobé access tokeny se obnovují podle potřeby.
- Při revokaci refresh tokenu je nutná opětovná autorizace.

2. Pub/Sub → Cloud Run Ingress
- Pub/Sub push používá OIDC autentizaci.
- Cloud Run ověřuje identitu volajícího.
- Pouze oprávněná servisní identita může vyvolat Ingress.

3. Cloud Tasks → Cloud Run Worker
- Cloud Tasks HTTP úlohy používají OIDC token.
- Worker ověřuje autorizaci prostřednictvím Cloud Run IAM.
- Neautorizované požadavky jsou odmítnuty.

4. Doba platnosti tokenů
- OIDC a access tokeny mají omezenou platnost.
- Servisní tokeny se získávají pro jednotlivá volání.
- Aplikace neudržuje dlouhodobé uživatelské sessions.

5. Secret management
- Gmail refresh token v Google Secret Manageru.
- Cloud Run používá servisní identity.
- Žádné OAuth tokeny ani statické servisní klíče v Git repozitáři.
- Přístupy k secrets jsou omezené pomocí IAM.

6. Bezpečnost
- HTTPS/TLS.
- Princip nejnižších oprávnění.
- Oddělené servisní identity pro Ingress, Worker a integrační volání.
- Cloud Run endpointy nejsou anonymně přístupné.
- Autentizační chyby jsou logované bez přístupových tokenů.

7. Testování
- Platný a neplatný OIDC token.
- Chybějící autentizace.
- Expirace Gmail access tokenu.
- Revokace Gmail refresh tokenu.
- Zamítnutý přístup k Secret Manageru.

CÍL:
Bezpečně autentizovat jednotlivé cloudové události bez potřeby vlastního systému dlouhodobých realtime sessions.

### Jak škáluje fan-out, connection limity a backpressure?

- ID: rt_scaling (doplňkové)
- Stav: **PŘEDPOKLAD**

EVENT SCALING & BACKPRESSURE – REPLY MCFLY

Aplikace nepoužívá WebSocket spojení ani realtime fan-out k uživatelům. Škálování řešíme pomocí Cloud Tasks a Cloud Run.

1. Příjem událostí
- Gmail Watch publikuje změny do Pub/Sub.
- Cloud Run Ingress přijímá krátké HTTPS požadavky.
- Ingress neprovádí AI inference.
- Synchronizace a zpracování se předávají do Cloud Tasks.

2. Sync Queue
- Maximálně jedna aktivní synchronizace dedikované Gmail schránky.
- PostgreSQL používá mailbox-level lease.
- Souběžné nebo duplicitní notifikace nezpůsobí souběžné konfliktní synchronizace.

3. Process Queue
- Výchozí limit: maximálně 3 současné email jobs.
- Cloud Run Worker: max. 3 instance.
- Concurrency: 1 požadavek na instanci.
- Každý Worker zpracovává jeden email job.

4. Backpressure
- Při vyšší zátěži Cloud Tasks omezuje dispatch rate a concurrency.
- Nezpracované úlohy zůstávají ve frontě.
- Worker nepřijímá nekontrolovaný počet souběžných AI požadavků.
- Cloud Tasks retry používá omezený exponential backoff.

5. Kapacitní omezení
- Gmail API kvóty.
- Gemini inference kvóty a latence.
- Cloud SQL počet spojení a výkon.
- Cloud Run CPU a paměť.
- Počet a velikost příloh.

6. Monitoring
- Počet čekajících Cloud Tasks úloh.
- Stáří nejstarší úlohy.
- Počet aktivních Worker instancí.
- Latence Gemini a Gmail API.
- PostgreSQL latence a počet spojení.
- Celková end-to-end latence.

7. Škálování
- Počet Worker instancí je konfigurovatelný.
- Cloud Tasks dispatch rate lze postupně zvýšit.
- Ingress a Worker škálují nezávisle.
- PostgreSQL a externí API kvóty určují skutečný maximální výkon.

8. Omezení 120 sekund
- Čekání ve frontě se započítává do end-to-end latence.
- Samotné škálování Cloud Run nezaručuje zpracování do 120 sekund.
- Při zátěžových testech změříme p95 a maximální latenci.
- Podle výsledků upravíme concurrency, počet instancí a API limity.

CÍL:
Zajistit kontrolované zpracování většího počtu e-mailů bez zahlcení Gemini, Gmail API nebo PostgreSQL.

Zvolený návrh je vhodný pro PoC a umožňuje postupné škálování bez zavedení Kubernetes nebo vlastního realtime serveru.

### Co uvidí uživatel, když realtime není dostupný?

- ID: rt_fallback (doplňkové)
- Stav: **PŘEDPOKLAD**

REALTIME FALLBACK – REPLY MCFLY

Aplikace nemá vlastní realtime frontend. Uživatel komunikuje prostřednictvím e-mailu a neočekává živé aktualizace stavu.

1. Běžný provoz
- Uživatel odešle e-mail.
- Gmail Watch automaticky spustí zpracování.
- Asistent odešle odpověď do původního vlákna.
- Uživatel vidí výslednou odpověď ve svém e-mailovém klientovi.

2. Dočasný výpadek notifikací
- Původní e-mail zůstává v Gmail schránce.
- Cloud Scheduler spustí kontrolní synchronizaci.
- Gmail History API doplní zmeškané změny.
- Zpráva se následně zařadí ke zpracování.

3. Výpadek Workeru
- Cloud Tasks zachovává čekající úlohy podle své retenční a retry konfigurace.
- Po obnově služby mohou být úlohy opět zpracovány.
- PostgreSQL zajišťuje deduplikaci.

4. Co vidí uživatel
- Žádnou vlastní realtime chybovou obrazovku.
- Původní odeslanou zprávu ve svém e-mailovém klientovi.
- Při dočasném výpadku dorazí odpověď později.
- Pokud zpracování trvale selže, automatická odpověď nemusí být doručena.
- Správce incident dohledá přes monitoring.

5. Bezpečné chybové odpovědi
- Pokud systém dokáže bezpečně identifikovat chybu a odeslat zprávu, může uživatele informovat e-mailem.
- Při DELIVERY_UNKNOWN nesmí bez ověření odeslat druhou odpověď.
- Automatické chybové odpovědi nesmějí vytvářet e-mailové smyčky.

6. SLA omezení
- Cílová doba běžného zpracování je pod 120 sekund.
- Při výpadku Gmail API, Gemini nebo databáze nelze tento limit garantovat.
- Překročení limitu se eviduje jako nesplnění výkonnostního cíle.
- Recovery řeší spolehlivost, nikoliv garantovanou okamžitou odpověď.

7. Testování
- Výpadek Pub/Sub doručování.
- Výpadek Cloud Run Workeru.
- Neplatný Gmail historyId.
- Nedostupná databáze.
- Nedostupné Gmail API.
- Ověření bezpečného obnovení bez duplicit.

CÍL:
Zachovat možnost obnovení automatického zpracování bez vlastního realtime fallback rozhraní.

### Jak otestuješ reconnect, ztrátu sítě a pořadí?

- ID: rt_testing (doplňkové)
- Stav: **PŘEDPOKLAD**

REALTIME, RECONNECT & RECOVERY TESTING – REPLY MCFLY

Použijeme pytest, mockované cloudové adaptéry a integrační/E2E testy v GCP PoC.

Aplikace nepoužívá WebSockets ani SSE. Testujeme obnovu komunikace mezi Gmail Watch, Pub/Sub, Cloud Tasks, Cloud Run a PostgreSQL.

1. Výpadek sítě a Pub/Sub doručování
- Simulovat nedostupnost Cloud Run Ingress.
- Ověřit opakované doručení Pub/Sub notifikace.
- Ověřit bezpečné zpracování po obnovení spojení.
- Zkontrolovat, že nevznikne duplicitní email job.

2. Výpadek Cloud Run Workeru
- Simulovat restart nebo nedostupnost Workeru.
- Ověřit retry pomocí Cloud Tasks.
- Ověřit zachování stavu úlohy v PostgreSQL.
- Po expiraci lease umožnit bezpečné převzetí úlohy.
- Zabránit přepsání stavu zastaralým Workerem.

3. Duplicitní události
- Doručit stejnou Pub/Sub notifikaci vícekrát.
- Opakovaně spustit Cloud Tasks požadavek pro stejný job_id.
- Ověřit UNIQUE(mailbox_id, gmail_message_id).
- Ověřit maximálně jednu automatickou odpověď.

4. Pořadí událostí
- Simulovat doručení Gmail notifikací mimo pořadí.
- Ověřit synchronizaci přes Gmail History API od posledního potvrzeného checkpointu.
- Ověřit, že opožděná notifikace nepřepíše novější checkpoint.
- Ověřit chronologické pořadí Conversation History.
- Ověřit správné pořadí zpracování zpráv stejného vlákna.

5. Ztracené notifikace
- Simulovat vynechání Gmail Watch/Pub/Sub události.
- Spustit kontrolní synchronizaci prostřednictvím Cloud Scheduler.
- Ověřit doplnění chybějících zpráv.
- Již zpracované zprávy nesmějí být znovu odeslány.

6. Neplatný Gmail historyId
- Simulovat odmítnutí zastaralého checkpointu Gmail History API.
- Spustit řízenou resynchronizaci schránky.
- Znovu vyhledat relevantní zprávy.
- Ověřit deduplikaci podle uložených Gmail message IDs.
- Pokud nelze bezpečně obnovit stav, zaznamenat incident.

7. Výpadek PostgreSQL
- Simulovat nedostupnost databáze během synchronizace.
- Ověřit, že se checkpoint neposune před bezpečným uložením práce.
- Po obnově zopakovat synchronizaci.
- Ověřit zachování integrity email_jobs a email_outbox.

8. Nejasné odeslání
- Simulovat úspěšné Gmail Send bez doručeného potvrzení.
- Označit úlohu jako DELIVERY_UNKNOWN.
- Před případným retry ověřit odeslání v Gmailu.
- Nevytvářet duplicitní odpověď.

9. Test souběžnosti a škálování
- Odeslat 1, 3 a 5 testovacích e-mailů současně.
- Ověřit omezení Cloud Tasks concurrency.
- Ověřit izolaci nezávislých vláken.
- Změřit čekání ve frontě a celkovou latenci.
- Ověřit splnění limitu pod 120 sekund v definované zátěži.

10. Akceptační kritéria
- Žádná potvrzená duplicitní automatická odpověď.
- Žádná ztracená zpráva v testovaném recovery scénáři.
- Správné pořadí konverzace v rámci Gmail vlákna.
- Bezpečná obnova po výpadku Workeru nebo sítě.
- Správná synchronizace Gmail historyId.
- Korektní chování stavového automatu.
- Evidence job_id, correlation_id, výsledku PASS/FAIL a latence.

11. Automatizace
- Unit testy: pytest s fake Gmail, Pub/Sub a Cloud Tasks adaptéry.
- Integrační testy: PostgreSQL, lease, transakce a deduplikace.
- E2E testy: skutečný Gmail → Pub/Sub → Cloud Tasks → Cloud Run → Gmail Reply.
- Chybové scénáře se spouštějí v izolovaném testovacím prostředí.

CÍL:
Prokázat, že event-driven architektura bezpečně zvládá výpadky, opakované a opožděné události bez ztráty zpráv a duplicitního odesílání.

Retry a recovery zvyšují spolehlivost, ale samy o sobě negarantují odpověď do 120 sekund během výpadku externích služeb.

## Otevřené formulářové blokery

- [ ] has_files: Nahrává nebo ukládá aplikace uživatelské soubory? — chybí zdroj / důkaz
- [ ] multitenant: Má více organizací/tenantů sdílet aplikaci? — předpoklad
- [ ] realtime: Potřebuješ realtime, websockety, push nebo streaming? — chybí zdroj / důkaz
- [ ] personal_data: Budeš zpracovávat osobní či jiné citlivé údaje? — chybí zdroj / důkaz
- [ ] integrations_flag: Budeš volat externí služby/API? — chybí zdroj / důkaz
- [ ] primary_user: Kdo je primární uživatel a jaké má potřeby? — předpoklad
- [ ] success_definition: Jak poznáš, že produkt řeší problém? — předpoklad
- [ ] mvp_scope: Co přesně patří do MVP? — chybí zdroj / důkaz
- [ ] out_of_scope: Co do první verze záměrně nepatří? — předpoklad
- [ ] value_proposition: Proč bude uživatel aplikaci používat? — předpoklad
- [ ] actor_roles: Jaké role a oprávnění má aplikace? — předpoklad
- [ ] user_inputs: Jaké vstupy uživatel poskytuje? — předpoklad
- [ ] happy_path: Popiš hlavní user flow od otevření až k výsledku. — předpoklad
- [ ] user_output: Co člověk uvidí při úspěchu a jak se k tomu vrátí? — předpoklad
- [ ] error_scenarios: Co uvidí při prázdném, chybném či duplicitním vstupu? — předpoklad
- [ ] functional_requirements: Jaké jsou funkční požadavky FR-01, FR-02 ...? — předpoklad
- [ ] acceptance_criteria: Jaká jsou AC-01, AC-02 ... (Given/When/Then)? — předpoklad
- [ ] business_rules: Jaká pravidla, validace a výpočty musí platit? — předpoklad
- [ ] forbidden_states: Jaké nepovolené stavy nesmějí nikdy vzniknout? — předpoklad
- [ ] entity_states: Jaké entity mění stav a jaké přechody jsou povolené? — předpoklad
- [ ] permissions_matrix: Která role smí kterou akci a nad čími daty? — předpoklad
- [ ] performance_target: Jaká je cílová odezva (např. p95) a jak ji změříš? — předpoklad
- [ ] traffic_estimate: Kolik uživatelů, požadavků a špiček očekáváš? — předpoklad
- [ ] availability_target: Jaký je požadavek na dostupnost a měřené období? — předpoklad
- [ ] recovery_targets: Jaké je RPO a RTO pro důležitá data? — předpoklad
- [ ] retention_policy: Jak dlouho a proč držíš data, logy a zálohy? — předpoklad
- [ ] budget: Jaký je měsíční strop nákladů a kdo hlídá odchylky? — předpoklad
- [ ] system_boundary: Co je uvnitř produktu a co patří externím systémům? — předpoklad
- [ ] architecture_style: Jaký architektonický styl volíš a proč? — předpoklad
- [ ] components: Vyjmenuj komponenty, jejich jedinečnou odpovědnost a vlastníka. — předpoklad
- [ ] component_flows: Popiš šipky komponent: kdo → kdo, protokol, sync/async, timeout. — předpoklad
- [ ] architecture_alternatives: Jaké aspoň 2 rozumné alternativy jsi zvážil a proč nevyhrály? — předpoklad
- [ ] tech_stack: Jaké konkrétní technologie/verze zvolíš pro UI, API, DB, infra a proč? — předpoklad
- [ ] trust_boundaries: Kde jsou hranice důvěry, veřejná síť a citlivá data? — předpoklad
- [ ] entities: Jaké jsou hlavní entity, atributy, ID a vztahy? — předpoklad
- [ ] data_owner: Kdo vlastní pravdivý stav každého typu dat? — předpoklad
- [ ] database_choice: Jaký DB/úložiště zvolíš a proč? — předpoklad
- [ ] data_schema: Jaké tabulky/collections a klíčové constrainty zavedeš? — předpoklad
- [ ] data_migrations: Jak budeš měnit schéma bez ztráty dat a s rollback plánem? — předpoklad
- [ ] data_backup: Co se zálohuje, jak často, kam a jak ověříš obnovení? — předpoklad
- [ ] data_deletion: Jak proběhne výmaz účtu/dat včetně kopií a expirací? — předpoklad
- [ ] api_scope: Které API endpointy/operace musí vzniknout? — předpoklad
- [ ] api_contracts: Jak vypadají request/response schémata včetně chyb? — předpoklad
- [ ] api_auth: Jak API ověří identitu a oprávnění pro každou operaci? — předpoklad
- [ ] api_errors: Jaká je jednotná chybová obálka a HTTP status kódy? — předpoklad
- [ ] api_versioning: Jaké je pravidlo verzování a kompatibility kontraktů? — předpoklad
- [ ] identity_provider: Jak bude fungovat registrace, login, reset a MFA/SSO? — předpoklad
- [ ] authorization_policy: Kde se serverově kontroluje přístup k objektům a rolím? — předpoklad
- [ ] security_requirements: Jaké jsou bezpečnostní požadavky a kontrola (např. OWASP ASVS)? — předpoklad
- [ ] secrets_management: Kde budou secrets, jak rotují a kdo má přístup? — předpoklad
- [ ] encryption: Jak chráníš data přenosem a v klidu a spravuješ klíče? — předpoklad
- [ ] threat_model: Jaké jsou 3 největší hrozby a obrany? — předpoklad
- [ ] privacy_basis: Pokud zpracováváš osobní data: účel, právní základ, role správce/zpracovatele? — předpoklad
- [ ] frontend_framework: Jakou frontend platformu/framework/versi použiješ a proč? — předpoklad
- [ ] frontend_routes: Jaké stránky, navigace a chráněné routy existují? — předpoklad
- [ ] frontend_responsibilities: Jaké chování patří do UI a co je vždy ověřováno backendem? — předpoklad
- [ ] frontend_states: Jak UI zobrazí loading, empty, success, error, retry a offline stav? — předpoklad
- [ ] backend_language: Jaký backend runtime/framework a konkrétní verzi zvolíš? — předpoklad
- [ ] module_structure: Jak bude vypadat struktura repozitáře a moduly? — předpoklad
- [ ] app_services: Jaké application services orchestruji use case? — předpoklad
- [ ] domain_rules: Jaká business pravidla patří do domain layer? — předpoklad
- [ ] interfaces: Jaká rozhraní/DTO/typy musí existovat? — předpoklad
- [ ] first_slice: Jaký je úplně první vertikální slice UI/API/DB/test/deploy? — předpoklad
- [ ] hosting_provider: Kde přesně poběží production a v jakém regionu? — předpoklad
- [ ] deployment_strategy: Jak bude aplikace zabalená a nasazená (PaaS, VM, containers)? — předpoklad
- [ ] environment_matrix: Jaká prostředí dev/test/staging/prod existují a jak se liší? — předpoklad
- [ ] ci_pipeline: Jaké kontroly musí projít PR před merge? — předpoklad
- [ ] cd_pipeline: Jak proběhne release automaticky/ručně a kdo schvaluje produkci? — předpoklad
- [ ] infra_as_code: Jak eviduješ infrastrukturu a reprodukuješ ji? — předpoklad
- [ ] env_secrets: Jak oddělíš konfiguraci a tajemství pro jednotlivá prostředí? — předpoklad
- [ ] rollback_plan: Jak se vrátíš na předchozí verzi včetně změn DB? — předpoklad
- [ ] test_strategy: Jak rozdělíš unit, integration, contract, E2E a manuální testy? — předpoklad
- [ ] critical_e2e: Které 3 klíčové cesty bude chránit automatický E2E test? — předpoklad
- [ ] test_data: Jak připravíš stabilní testovací data bez produkčních osobních údajů? — předpoklad
- [ ] quality_gates: Co musí projít před merge a před release? — předpoklad
- [ ] uat_owner: Kdo provede a schválí UAT s konkrétními AC? — předpoklad
- [ ] failure_tests: Jak otestuješ timeout, výpadek DB, chybné API a retry? — předpoklad
- [ ] monitoring_scope: Jaké metriky pro uživatele a business flow měříš? — předpoklad
- [ ] logs_traces: Jaké logy, traces a correlation IDs zavedeš bez úniku dat? — předpoklad
- [ ] alerts: Jaké alerty se spouštějí, při jaké hranici a komu? — předpoklad
- [ ] on_call: Kdo řeší výpadky, v jakých hodinách a jak ho kontaktovat? — předpoklad
- [ ] incident_runbook: Jak postupovat při 5xx spike, pomalé DB a pádu závislosti? — předpoklad
- [ ] recovery_drill: Kdy a jak ověříš obnovu ze zálohy proti RTO/RPO? — předpoklad
- [ ] milestones: Jaké jsou hlavní milníky: skeleton, MVP, beta, production? — předpoklad
- [ ] walking_skeleton: Jak otestuješ cestu commit -> CI -> staging -> jednoduché UI/API -> DB? — předpoklad
- [ ] first_ticket: Jak vypadá první implementační ticket (co / proč / AC / test / done)? — předpoklad
- [ ] delivery_dependencies: Co musí být rozhodnuto/koupeno/schváleno před kódem? — předpoklad
- [ ] next_action: Jaký je nejbližší přesný krok, který můžeš udělat dnes? — předpoklad
- [ ] release_owner: Kdo schválí produkční release a kdo je na místě při nasazení? — předpoklad
- [ ] release_plan: Jaký je přesný postup nasazení včetně pořadí migrací? — předpoklad
- [ ] preflight_checklist: Jaké předrelease kontrolní body musí být doložené? — předpoklad
- [ ] smoke_tests: Jaké smoke testy se provedou bezprostředně po deploy? — předpoklad
- [ ] rollback_trigger: Které metriky či chyby spustí okamžitý rollback? — předpoklad
- [ ] rollback_exercise: Kdy byl naposledy odzkoušen návrat/obnova a jaký je důkaz? — předpoklad
- [ ] production_access: Kdo má přístup do produkce a jak se auditují změny? — předpoklad
- [ ] launch_monitoring: Jaké dashboardy a alerty sleduješ prvních 24–72 h? — předpoklad
- [ ] post_launch_metrics: Kdy ověříš úspěšnost proti produktovému cíli? — předpoklad
- [ ] ai_use_case: Kde přesně AI rozhoduje/generuje a proč nestačí deterministické řešení? — předpoklad
- [ ] ai_provider: Jaký model/provider/verzi smíš použít a kde se zpracují data? — předpoklad
- [ ] ai_data_policy: Jaká data mohou do modelu, jaký je retention a souhlas? — předpoklad
- [ ] ai_eval: Jaká je offline eval sada a akceptační práh kvality? — předpoklad
- [ ] ai_failure: Co se stane při halucinaci, timeoutu, nevhodném výstupu a outage? — předpoklad
- [ ] ai_costs: Jaký token/call budget, limity a náklady na uživatele/job? — předpoklad
- [ ] files_types: Jaké formáty, velikosti a počet souborů dovolíš? — předpoklad
- [ ] files_validation: Jak ověříš skutečný typ, velikost a škodlivý obsah? — předpoklad
- [ ] files_storage: Kde se soubory drží a jak se řídí přístup? — předpoklad
- [ ] files_lifecycle: Kdy a jak se soubory mažou včetně záloh? — předpoklad
- [ ] rt_transport: Jaký protokol (SSE/WS/push) zvolíš a proč? — předpoklad
- [ ] rt_ordering: Jak klient rozpozná duplicity, zpoždění a pořadí? — předpoklad
- [ ] rt_reconnect: Jak proběhne reconnect a doplnění zmeškaného stavu? — předpoklad
