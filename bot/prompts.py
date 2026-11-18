"""Every prompt sent to the AI providers, in one place."""

TRANSLATE_PROMPT = (
    "Traduis ce texte en français, intégralement, sans rien omettre ni résumer. "
    "Si le texte est déjà en français, retourne-le tel quel, sans explication. "
    "Quelle que soit la langue source (russe, chinois, arabe, etc.), la réponse doit être "
    "entièrement en français. Réponds uniquement avec la traduction.\n\n"
)

SUMMARY_PROMPT = (
    "Résume ce tweet EN FRANÇAIS, quelle que soit la langue du tweet (jamais en russe, chinois, "
    "arabe ou autre langue). S'il contient une citation directe (propos rapportés), reproduis-la "
    "mot pour mot entre guillemets (traduite en français), puis résume en 2 lignes : qui a dit quoi "
    "et le contexte. Sinon, résume-le en 3 lignes courtes et précises. "
    "Ajoute ensuite une ligne vide et une section commençant par \"📊 Impact :\" qui explique en "
    "1-2 lignes pourquoi cela compte pour les marchés (politique monétaire, inflation, croissance, "
    "risque, etc.). Chaque phrase doit être complète. Réponds uniquement en français, "
    "sans introduction.\n\n"
)

CLASSIFY_PROMPT = (
    "Génère 1 à 5 hashtags en FRANÇAIS pour catégoriser ce tweet financier. "
    "Inclus : (1) l'institution/thème macro (ex: #FED #BCE #BoE #BoJ #Inflation #Taux #PIB #Emploi), "
    "et (2) le ou les instruments financiers impactés parmi : "
    "#Actions #Obligations #Or #Pétrole #Devises #Dollar #Euro #Crypto #Matières #Immobilier. "
    "Réponds uniquement avec les hashtags séparés par des espaces, rien d'autre.\n\n"
)

RELEVANCE_PROMPT = (
    "Does this tweet contain a market-moving signal? "
    "A market-moving signal is actionable information such as: interest rate decisions, "
    "inflation or GDP data releases, central bank policy changes, recession warnings, "
    "earnings surprises, or breaking financial news.\n"
    "Promotional content is NEVER a market-moving signal: answer 'NO' for ads, sponsored posts, "
    "self-promotion (newsletters, courses, webinars, apps, brokers, trading signals, subscriptions), "
    "promo codes, giveaways, affiliate links or invitations to subscribe, sign up or buy.\n"
    "Respond with ONLY 'YES' or 'NO'.\n\n"
)

PROMO_PROMPT = (
    "Ce tweet est-il de la promotion ou de la publicité ? C'est le cas s'il fait la "
    "promotion d'un produit, service, abonnement, newsletter, formation, webinaire, "
    "application, broker, code promo, concours/giveaway, lien d'affiliation, ou s'il "
    "invite à s'abonner, s'inscrire ou acheter. Une information de marché ou une actualité "
    "n'est PAS de la promotion.\n"
    "Réponds uniquement par 'OUI' ou 'NON'.\n\n"
)

FRENCH_PROMPT = (
    "Ce texte est-il rédigé entièrement en français (hors noms propres, sigles, tickers et "
    "citations très courtes) ? Toute autre langue différente du français est NON.\n"
    "Réponds uniquement par 'OUI' ou 'NON'.\n\n"
)
