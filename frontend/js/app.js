/**
 * Personal Finance Dashboard v2.0 - Frontend Application
 * Handles data fetching, chart rendering, and UI updates
 */

// Configuration - Auto-detects production vs development
// In production the backend serves both the API and this HTML from the same origin.
// In local dev we typically run the frontend on :3000 and the backend on :8000.
const isProduction = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
const API_BASE_URL = isProduction
    ? `${window.location.origin}/api`
    : 'http://localhost:8000/api';

const CONFIG = {
    API_BASE_URL: API_BASE_URL,
    REFRESH_INTERVAL: 60000, // 1 minute
    CHART_COLORS: ['#00d4aa', '#6366f1', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6'],
};

console.log('FinTrack API URL:', CONFIG.API_BASE_URL);

// Export for other scripts
window.API_BASE_URL = CONFIG.API_BASE_URL;

// State
let portfolioData = null;
let charts = {
    portfolio: null,
    type: null,
    broker: null,
    currency: null,
    benchmark: null
};
let currentPeriod = 30;
let sortColumn = 'market_value';
let sortDirection = 'desc';

// Single source of truth for asset display names/icons/colors — verified 2026-08
// against the real Trade Republic / MyInvestor / Kraken records. Every other
// script (asset-analysis.js, portfolio-manager.js, transactions.js, backtest.js)
// reads this same object; do not declare a second copy anywhere, and do not
// "correct" an entry without re-checking a real CSV/broker export first
// (LYX0F.DE and IE00BYX5NX33 were swapped here for months, and this dict used
// to also mislabel the Gold ETC, IE00B4ND3602, as "iShares MSCI World").
// `short` is for tight spaces (correlation matrix headers, chart legends)
// where "Fidelity MSCI World P-Acc" would overflow — keep it recognizable
// at a glance, matching how the user talks about these positions.
// `about` is static, hand-written educational content (what it is, what it
// tracks/how it works, brief history) — deliberately NOT LLM-generated, since
// facts like inception dates or index methodology are exactly the kind of
// thing a model can quietly get wrong. Verify before editing, same rule as
// the rest of this object.
const ASSET_DISPLAY_NAMES = {
    'BTC': { name: 'Bitcoin', short: 'Bitcoin', icon: '₿', color: '#f7931a', about:
        `Bitcoin es la primera criptomoneda descentralizada, descrita en un whitepaper publicado en octubre de 2008 bajo el seudónimo Satoshi Nakamoto (su identidad real nunca se ha confirmado), poco después de la crisis financiera de ese año. La red arrancó el 3 de enero de 2009. La motivación explícita del whitepaper era eliminar la necesidad de un intermediario de confianza (un banco) para transferir valor entre dos partes.

Funciona sobre una blockchain: un libro de cuentas público replicado por miles de nodos independientes. Las transacciones se validan mediante "prueba de trabajo" (proof-of-work) — los mineros compiten resolviendo cálculos costosos en energía (hashing SHA-256), y quien lo logra primero añade el siguiente bloque (cada ~10 minutos) y recibe una recompensa en bitcoins nuevos más las comisiones del bloque. La "dificultad" del cálculo se ajusta automáticamente cada 2016 bloques para que el ritmo de creación de bloques se mantenga estable aunque haya más o menos mineros conectados.

Su rasgo distintivo es la oferta fija: nunca habrá más de 21 millones de bitcoins. Cada 210.000 bloques (~4 años) ocurre el "halving", que reduce a la mitad la recompensa de los mineros: ha pasado en 2012, 2016, 2020 y 2024, y cada vez ha ido acompañado de un debate sobre si "ya está descontado en el precio" o si sigue moviendo el mercado por la caída en la oferta nueva. Se estima que el último bitcoin se minará alrededor del año 2140.

Aunque el diseño original era sobre todo "dinero digital" para pagos, el uso dominante hoy es como reserva de valor especulativa — la narrativa de "oro digital". Dos hitos cambiaron su relación con las finanzas tradicionales: en septiembre de 2021 El Salvador lo adoptó como moneda de curso legal (el primer país en hacerlo), y en enero de 2024 la SEC de EE. UU. aprobó los primeros ETFs de Bitcoin al contado (entre ellos el IBIT de BlackRock), abriendo la puerta a que fondos de pensiones y gestoras tradicionales inviertan sin tener que custodiar las claves privadas ellos mismos. Empresas como MicroStrategy (ahora Strategy), con Michael Saylor a la cabeza, han acumulado bitcoin como activo de tesorería corporativa desde 2020, una estrategia que ha sido imitada y también criticada por el riesgo de apalancamiento que conlleva.

Técnicamente ha evolucionado poco comparado con blockchains más recientes por diseño: los cambios se aprueban por consenso lento entre desarrolladores, mineros y operadores de nodos (vía "BIPs", Bitcoin Improvement Proposals), sin ninguna empresa ni fundación al mando. Las dos actualizaciones más relevantes de la última década fueron SegWit (2017, mejora de capacidad y corrige un fallo técnico) y Taproot (2021, mejora la privacidad y permite transacciones algo más complejas). El desacuerdo sobre si aumentar el tamaño de bloque para más capacidad llevó a una escisión (fork) de la red en agosto de 2017 que creó Bitcoin Cash, una moneda distinta con muchísima menos adopción hoy. La Lightning Network, una capa construida encima de Bitcoin, permite pagos casi instantáneos y con comisiones mínimas para quien la usa, pensada para micropagos que en la cadena principal serían demasiado lentos o caros.

Riesgos a tener en cuenta: es el activo más volátil de la cartera tras las memecoins, su valor no está respaldado por flujos de caja ni activos (a diferencia de una acción o un bono), ha sufrido colapsos de exchanges e intermediarios (Mt. Gox en 2014, FTX en 2022 — aunque este último afectaba más a otras criptomonedas, dañó la confianza del sector en general), y el consumo energético de la minería sigue siendo objeto de debate medioambiental, aunque una parte creciente proviene de energía renovable o gas que de otro modo se quemaría sin uso.` },
    'ETH': { name: 'Ethereum', short: 'Ethereum', icon: 'Ξ', color: '#627eea', about:
        `Ethereum es una plataforma descentralizada para ejecutar "contratos inteligentes" — programas que se ejecutan automáticamente si se cumplen ciertas condiciones, sin intermediario —, lanzada en julio de 2015 por Vitalik Buterin junto a varios cofundadores (entre ellos Gavin Wood, autor del whitepaper técnico, y Joseph Lubin, que luego fundó ConsenSys). A diferencia de Bitcoin, pensado sobre todo como dinero digital, Ethereum es infraestructura genérica: sobre ella se construyen exchanges descentralizados, préstamos sin banco (DeFi), tokens NFT, stablecoins como USDC/USDT (que en su mayoría circulan sobre Ethereum o sus capas secundarias) y organizaciones autónomas descentralizadas (DAOs).

Su historia técnica ha sido de actualizaciones constantes, a diferencia del conservadurismo deliberado de Bitcoin. La más importante fue "The Merge" en septiembre de 2022: el cambio del mecanismo de validación de "prueba de trabajo" (minería con GPUs, igual que Bitcoin) a "prueba de participación" (proof-of-stake, donde los validadores bloquean ETH como garantía en vez de gastar electricidad), que redujo el consumo energético de la red en más de un 99%. En abril de 2023 la actualización Shanghai/Shapella permitió por primera vez retirar el ETH que se había bloqueado en staking desde 2020, cerrando el ciclo. Antes de esto, en 2016, un fallo explotado en un contrato inteligente conocido como "The DAO" provocó el robo de millones de dólares en ETH y llevó a una decisión muy controvertida: revertir la cadena para devolver los fondos, lo que dividió a la comunidad y creó una segunda cadena, Ethereum Classic, que mantuvo el histórico "inmutable" original.

El token ETH sirve para pagar el "gas" (la comisión) de cada operación en la red — cuanto más congestionada está la red, más caro el gas — y para hacer staking, con un rendimiento anual variable a cambio de ayudar a validar la red. No tiene un límite de oferta fijo como Bitcoin, pero desde la actualización EIP-1559 (2021) una parte de cada comisión se "quema" permanentemente, lo que hace que la oferta pueda incluso reducirse en periodos de mucho uso — un diseño económico bastante distinto al de Bitcoin.

El principal reto de Ethereum ha sido siempre la escalabilidad: en momentos de mucha demanda las comisiones se han disparado a decenas de dólares por operación, lo que ha impulsado el auge de "capas 2" (Arbitrum, Optimism, Base y otras) que procesan transacciones fuera de la cadena principal y solo se asientan en ella periódicamente, mucho más baratas y rápidas. Su gran competencia son precisamente esas capas 2 y otras blockchains "de capa 1" (Solana, entre ellas), en una disputa constante sobre dónde acaba viviendo la actividad y el valor.` },
    'SOL': { name: 'Solana', short: 'Solana', icon: '◎', color: '#00ffa3', about:
        `Solana es una blockchain lanzada en marzo de 2020 por Anatoly Yakovenko (ex-ingeniero de Qualcomm) junto a Raj Gokal, diseñada desde el inicio para procesar muchísimas más transacciones por segundo que Bitcoin o Ethereum — miles frente a decenas —, a cambio de mayor centralización técnica (requiere hardware potente para ser validador, lo que reduce cuántos actores pueden participar) y un historial notable de caídas de red completas (varias interrupciones entre 2021 y 2022, algunas de horas, por saturación o fallos de consenso, aunque su fiabilidad ha mejorado desde entonces).

Combina "prueba de participación" con una innovación propia, "prueba de historia" (proof-of-history): en vez de que los validadores negocien el orden de las transacciones en tiempo real, cada una lleva una marca de tiempo criptográfica verificable que permite ordenarlas de antemano, acelerando notablemente el proceso de consenso frente a blockchains tradicionales.

Su caso de uso dominante es donde la velocidad y el coste importan más que la descentralización máxima: exchanges descentralizados de alta frecuencia, emisión masiva de NFTs y, sobre todo desde 2023-2024, la explosión de "memecoins" creadas y negociadas en cuestión de minutos gracias a plataformas como pump.fun — un fenómeno que ha disparado tanto la actividad en la red como las críticas por la cantidad de estafas y tokens sin ningún valor que genera. El token SOL sirve para pagar comisiones de red (típicamente fracciones de céntimo) y para hacer staking.` },
    'DOGE': { name: 'Dogecoin', short: 'Dogecoin', icon: '🐕', color: '#c3a634', about:
        `Dogecoin nació el 6 de diciembre de 2013 como una broma entre dos ingenieros de software (Billy Markus y Jackson Palmer), basada en el meme del perro Shiba Inu "Doge" que circulaba por internet en aquellos años. Técnicamente es una copia (fork) de Litecoin, que a su vez es una copia de Bitcoin, y usa el mismo sistema de "prueba de trabajo" — de hecho comparte minería con Litecoin desde 2014 (merged mining), por lo que su seguridad depende en parte de esa red.

A diferencia de Bitcoin, no tiene límite máximo de unidades: se crean alrededor de 5.000 millones de DOGE nuevos cada año de forma indefinida, lo que lo hace estructuralmente inflacionario por diseño — sus propios creadores lo pensaron así precisamente para desincentivar acumularlo como reserva de valor y fomentar gastarlo, aunque en la práctica ha terminado usándose sobre todo como activo especulativo.

No ha recibido ninguna actualización tecnológica relevante en años ni tiene una hoja de ruta de desarrollo activa comparable a Bitcoin o Ethereum. Su relevancia viene enteramente de la cultura de internet: se disparó en 2021 durante la mayor ola especulativa cripto de esa época, impulsada en gran parte por menciones repetidas de Elon Musk en redes sociales (incluida la etapa en la que la red social X usó temporalmente su logo). No tiene equipo fundador activo con autoridad sobre el proyecto ni casos de uso institucional relevantes — es, por diseño y por historia, de los activos más especulativos y dependientes del sentimiento de toda la cartera.` },
    'PEPE': { name: 'Pepe', short: 'Pepe', icon: '🐸', color: '#4caf50', about:
        `PEPE es una criptomoneda "meme" lanzada en abril de 2023 sobre la red de Ethereum, inspirada en el personaje de internet "Pepe the Frog" (creado originalmente por el dibujante Matt Furie en 2005, sin ninguna relación con el proyecto cripto). No tiene equipo fundador público conocido, whitepaper técnico, ni ningún caso de uso más allá de la especulación y la cultura de internet cripto.

Su valor se basa exclusivamente en la demanda especulativa y la actividad de comunidades en redes sociales — junto con Dogecoin, es de los activos con más volatilidad de toda la cartera. Es un token estándar (ERC-20) sin ningún mecanismo económico especial, sin quema de tokens, sin staking y sin ninguna función más allá de transferirse. Pertenece a la ola de "memecoins" que se disparó en 2023-2024 en Ethereum y, sobre todo, en Solana — un fenómeno donde miles de tokens similares se lanzan cada día y la inmensa mayoría acaban sin ningún valor; PEPE es una de las pocas que ha mantenido capitalización relevante en el tiempo, pero eso no la hace menos especulativa.` },
    'IE00BYX5NX33': { name: 'Fidelity MSCI World P-Acc', short: 'MSCI World', icon: '🌍', color: '#2196f3', about:
        `Fondo indexado (no cotiza como un ETF; se compra/vende directamente a través del gestor, en este caso vía MyInvestor, a precio de cierre diario en vez de en tiempo real) gestionado por Fidelity, que replica el índice MSCI World: en torno a 1.400-1.500 empresas grandes y medianas de 23 países "desarrollados" según la clasificación de MSCI (no incluye mercados emergentes como China, India o Brasil — para eso existe el MSCI ACWI, que sí los añade). EE. UU. suele pesar en torno al 65-70% del índice, muy por encima de su peso en la economía mundial, seguido de lejos por Japón, Reino Unido, Francia y otros mercados desarrollados; dentro de EE. UU. las mismas grandes tecnológicas (Apple, Microsoft, Nvidia...) que dominan el S&P 500 también dominan aquí, así que el "MSCI World" está menos diversificado sectorialmente de lo que su nombre sugiere.

El índice lo mantiene y revisa MSCI Inc., una empresa independiente (no el propio Fidelity), que decide qué entra y sale según capitalización, liquidez y free-float (porcentaje de acciones realmente negociables). La réplica de Fidelity es física por muestreo: no compra literalmente las ~1.500 empresas en la proporción exacta del índice, sino una selección representativa optimizada para minimizar el error de seguimiento (tracking error) frente al índice real, algo habitual en fondos de este tamaño.

"P-Acc" significa clase "P" (para inversores particulares, sin mínimo alto de inversión, a diferencia de las clases institucionales) y "Acc" (acumulación): los dividendos que reparten las empresas no se pagan al inversor, se reinvierten automáticamente dentro del fondo, lo que compone el crecimiento con el tiempo sin que tengas que reinvertirlos tú mismo (y sin generar un hecho fiscal en cada reparto).

Es un fondo domiciliado en Irlanda (estructura UCITS, el estándar regulatorio europeo para fondos y ETFs), lo que en España permite traspasos entre fondos sin tributar hasta el reembolso final — una ventaja fiscal real frente a comprar acciones sueltas o ETFs, donde cada venta tributa. Es de gestión pasiva: no intenta batir al mercado ni elegir qué empresas van a ir mejor, solo replicarlo al menor coste posible, apostando por la evidencia histórica de que superar al mercado de forma consistente es muy difícil incluso para gestores profesionales.` },
    'IE00B4ND3602': { name: 'iShares Physical Gold ETC', short: 'Oro', icon: '🥇', color: '#ffd700', about:
        `No es un fondo de acciones de mineras de oro (eso sería más volátil y dependería también de la gestión de esas empresas), sino un ETC (Exchange Traded Commodity) respaldado por oro físico real almacenado en bóvedas seguras auditadas periódicamente. Cada participación representa una fracción de una onza troy de oro, y su precio sigue casi uno a uno la cotización del oro al contado (spot), menos una pequeña comisión de gestión anual.

El oro se ha usado como reserva de valor durante milenios, mucho antes de que existiera el dinero fiduciario moderno; a diferencia de las divisas, ningún banco central puede "imprimir" más oro, y su oferta crece muy lentamente (la minería global añade solo un 1-2% de las reservas existentes cada año). Suele comportarse como refugio en momentos de inflación alta, crisis geopolíticas, guerras o caídas fuertes de bolsa, aunque esa correlación negativa con las acciones no es constante — hay periodos (como parte de 2013 o 2022) donde ambos han caído a la vez.

A diferencia de una acción o un bono, el oro no genera dividendos, intereses ni beneficios: su "rentabilidad" depende íntegramente de que otro esté dispuesto a pagar más por él en el futuro, lo que hace su valoración un ejercicio distinto al de valorar un negocio. Muchos bancos centrales (China, Rusia, India, Turquía entre los más activos en los últimos años) han aumentado sus reservas de oro precisamente para reducir su dependencia del dólar estadounidense como activo de reserva — un factor estructural de demanda que ha ganado peso en el debate sobre el papel del oro en el sistema financiero actual.` },
    'LYX0F.DE': { name: 'Amundi Nasdaq-100', short: 'Nasdaq-100', icon: '📈', color: '#1976d2', about:
        `ETF gestionado por Amundi (que absorbió en 2021 la gama de fondos Lyxor de Société Générale) que replica el índice Nasdaq-100: las 100 mayores empresas no financieras cotizadas en el mercado Nasdaq de EE. UU., ponderadas por capitalización bursátil con algunos límites internos para evitar que una sola empresa pese demasiado (el índice se "reequilibra" de forma especial si una compañía supera cierto umbral de peso, como pasó con Apple en 2011 y 2023).

Está muy concentrado en tecnología — Apple, Microsoft, Nvidia, Amazon, Meta, Alphabet y Broadcom suelen representar más de la mitad del índice entre las siete —, por lo que aporta más potencial de crecimiento pero también más volatilidad y menos diversificación real que un índice amplio como el S&P 500 (que incluye financieras, salud, industria...) o el MSCI World. Al excluir explícitamente el sector financiero, tampoco sufrió tan de lleno la crisis bancaria de 2008 como otros índices, aunque sí el batacazo de las "puntocom" en 2000-2002, cuando cayó más de un 75% desde máximos — el precedente histórico que más se cita cuando se debate si la concentración tecnológica actual es sostenible.

El Nasdaq-100 se creó en 1985 y desde entonces ha cambiado radicalmente de composición: en sus primeros años tenía mucho peso de biotecnología y telecomunicaciones, y ha ido virando hacia el software y la computación en la nube, y ahora hacia la infraestructura de inteligencia artificial. Su composición se revisa trimestralmente para mantener solo las empresas más grandes y líquidas que cumplen los requisitos del índice.` },
    'VVSM.DE': { name: 'VanEck Semiconductor', short: 'Semiconductores', icon: '💾', color: '#9c27b0', about:
        `Replica el índice MVIS US Listed Semiconductor 25, formado por unas 25 empresas cotizadas en EE. UU. relacionadas con el diseño, fabricación y equipamiento de semiconductores (chips) — desde diseñadoras "fabless" (que no fabrican, solo diseñan) como Nvidia, AMD o Qualcomm, hasta fabricantes de la maquinaria de precisión necesaria para producir chips, como ASML (empresa neerlandesa pero cotizada también en EE. UU.), que tiene el monopolio mundial de la litografía ultravioleta extrema (EUV) imprescindible para los chips más avanzados.

Los semiconductores son el componente físico que hace posible toda la computación moderna — ordenadores, móviles, coches, electrodomésticos y, sobre todo desde 2023, los centros de datos que entrenan y ejecutan modelos de inteligencia artificial, el principal motor de la demanda reciente del sector—, por lo que suele moverse en ciclos muy marcados: fuertes subidas en fases de expansión de la demanda y correcciones bruscas cuando esa demanda se satura, cae la inversión en capacidad, o surgen restricciones geopolíticas (las tensiones comerciales entre EE. UU. y China sobre exportación de chips avanzados y maquinaria de fabricación son un riesgo estructural del sector desde hace varios años, dado que Taiwán —vía TSMC— concentra la inmensa mayoría de la fabricación de chips más avanzados del mundo, lo que también lo convierte en un riesgo geopolítico central si la situación con China se deteriorase).` },
    'QDVF.DE': { name: 'iShares S&P500 Energy', short: 'S&P Energía', icon: '⚡', color: '#ff9800', about:
        `Replica el subíndice de energía dentro del S&P 500: empresas estadounidenses grandes dedicadas a la extracción, refino y distribución de petróleo y gas (ExxonMobil y Chevron suelen ser sus mayores posiciones, ya que el sector de energía del S&P 500 apenas incluye renovables puras — esas suelen cotizar en índices "clean energy" distintos).

Su cotización está fuertemente correlacionada con el precio del petróleo y el gas natural, y por tanto con decisiones de producción de la OPEP+ (el cártel de países exportadores más Rusia y aliados), tensiones geopolíticas en zonas productoras (Oriente Medio, Rusia) y el ciclo económico global — más actividad industrial implica más demanda energética. Es un sector que históricamente reparte dividendos altos y ha demostrado ser un buen amortiguador cuando sube la inflación (los precios de la energía suelen ser de los primeros en subir), aunque compite a largo plazo con la transición hacia energías renovables y con la presión regulatoria/social sobre los combustibles fósiles, un debate que pesa sobre la valoración a largo plazo del sector.` },
    'NUKL.DE': { name: 'VanEck Uranium & Nuclear', short: 'Uranio/Nuclear', icon: '☢️', color: '#8bc34a', about:
        `Invierte en empresas de toda la cadena de la energía nuclear: minería y enriquecimiento de uranio (el combustible), diseño y construcción de reactores, y compañías eléctricas que operan centrales nucleares. Incluye tanto mineras puras (Cameco, Kazatomprom) como conglomerados industriales con divisiones nucleares (como algunos fabricantes de turbinas y equipos).

Es un sector nicho, con relativamente pocas empresas puras cotizadas, y por tanto volátil, muy sensible a decisiones políticas: cierres o reaperturas de centrales (Alemania cerró las suyas en 2023, mientras Francia, Japón y otros países han revertido planes de cierre), nuevas licencias, y accidentes históricos que marcaron generaciones enteras de política energética (Three Mile Island 1979, Chernóbil 1986, Fukushima 2011 —tras el cual varios países frenaron en seco sus programas nucleares durante años—).

El resurgir del interés por la nuclear desde 2022 tiene dos motores concretos: la búsqueda de alternativas al gas ruso tras la invasión de Ucrania, y la necesidad de electricidad estable, constante y sin emisiones de CO2 para alimentar la demanda eléctrica creciente de los centros de datos de inteligencia artificial — varias grandes tecnológicas han firmado acuerdos directos con operadores nucleares (incluyendo reactores modulares pequeños, SMR, todavía en fase temprana de desarrollo comercial) para asegurarse suministro a largo plazo.` },
    'BTEC.L': { name: 'iShares Nasdaq Biotech', short: 'Biotech', icon: '🧬', color: '#00bcd4', about:
        `Replica el índice Nasdaq Biotechnology, compuesto por empresas biotecnológicas y farmacéuticas cotizadas en el Nasdaq — desde grandes farmacéuticas consolidadas con múltiples fármacos ya aprobados y en el mercado, hasta compañías pequeñas ("clinical-stage") en fase de investigación clínica sin ingresos todavía, cuyo único activo real es la posibilidad de que su molécula funcione.

Es un sector de alto riesgo/alta recompensa muy particular: el valor de una empresa biotecnológica pequeña puede duplicarse o perder el 80% de su valor de la noche a la mañana según el resultado de un ensayo clínico de fase 2 o 3, o una decisión de aprobación (o rechazo) de la FDA (la agencia reguladora de medicamentos de EE. UU.) — son movimientos binarios, no graduales, porque el mercado revalúa de golpe la probabilidad de éxito del producto. Al diversificar entre muchas compañías del índice, el ETF reduce —pero no elimina— ese riesgo de apostar por el resultado de un único ensayo. El sector también depende mucho del ciclo de tipos de interés: muchas biotecnológicas pequeñas no generan beneficios y financian su investigación con deuda o ampliaciones de capital, lo que las hace más sensibles a la subida de tipos que empresas rentables.` },
    'COPX.L': { name: 'Global X Copper Miners', short: 'Cobre', icon: '🔶', color: '#b87333', about:
        `Replica un índice de empresas dedicadas a la extracción y producción de cobre en todo el mundo (grandes mineras diversificadas con negocio de cobre como Freeport-McMoRan o Southern Copper, junto a productoras más puras). El cobre es un metal industrial clave — se usa en cableado eléctrico, construcción, electrodomésticos y, cada vez más, en la transición energética: un coche eléctrico usa varias veces más cobre que uno de combustión, y las redes eléctricas, paneles solares y turbinas eólicas también son intensivas en cobre —, por lo que su demanda está ligada tanto al crecimiento industrial tradicional como a la electrificación de la economía.

A diferencia del oro, el cobre no se considera un refugio, sino un termómetro del ciclo económico —de hecho se le llama a veces "Dr. Copper" precisamente por su fama de anticipar giros económicos—: sube cuando se espera más actividad industrial (sobre todo construcción en China, el mayor consumidor mundial) y baja cuando se teme una desaceleración. Un riesgo estructural del sector es que abrir una mina nueva de cobre tarda típicamente más de una década entre exploración, permisos y construcción, así que la oferta responde muy despacio a los picos de demanda —lo que puede generar ciclos de precios más extremos que en otras materias primas—.` },
    'JEDI.DE': { name: 'VanEck Space Innovators', short: 'Espacio', icon: '🚀', color: '#673ab7', about:
        `Invierte en empresas de la cadena de valor espacial: fabricantes de satélites, lanzadores (incluyendo SpaceX antes de su salida a bolsa, y ahora directamente el propio SPCX de esta cartera), comunicaciones satelitales, y compañías que dependen de infraestructura espacial para su negocio principal, como proveedores de imágenes satelitales, navegación GPS de precisión o sensores de observación de la Tierra.

Es un sector todavía emergente y con relativamente pocas empresas puras cotizadas (muchas de las más conocidas, como la propia SpaceX durante casi dos décadas, o Blue Origin, siguen o siguieron siendo privadas), impulsado sobre todo por la caída drástica de costes de lanzamiento gracias a los cohetes reutilizables — el coste por kilo puesto en órbita se ha reducido en más de un 90% desde la era del transbordador espacial — y por la multiplicación de aplicaciones comerciales del espacio: internet por satélite en órbita baja (Starlink de SpaceX, Kuiper de Amazon, OneWeb), observación de la Tierra para agricultura y seguros, y un gasto militar y de defensa creciente en capacidades espaciales. Al ser un sector joven con muchas empresas pequeñas y sin beneficios todavía, su volatilidad es alta y depende mucho del sentimiento sobre "temas de futuro" más que de beneficios actuales — es, junto a la biotecnología, de los sectores más especulativos de la cartera dentro de la parte no cripto.` },
    'PLTR': { name: 'Palantir Technologies', short: 'Palantir', icon: '🔮', color: '#000000', about:
        `Empresa estadounidense de software de análisis de datos fundada en 2003 por Peter Thiel (también cofundador de PayPal e inversor temprano en Facebook), Alex Karp (su CEO) y otros, con fuertes vínculos iniciales con agencias de inteligencia y defensa de EE. UU.: su primer gran cliente fue la CIA, a través de su brazo inversor In-Q-Tel, y durante más de una década su negocio dependió casi exclusivamente de contratos gubernamentales y de defensa — algo que sigue generando debate sobre los límites éticos del uso de sus herramientas de vigilancia y análisis masivo de datos por parte de gobiernos y ejércitos.

Sus dos productos principales son Gotham (para gobiernos, defensa e inteligencia — usado, por ejemplo, en la localización de Osama bin Laden según ha trascendido públicamente) y Foundry (su versión adaptada para empresas privadas): ambas son plataformas que integran datos dispersos y de formatos distintos dentro de una organización para que humanos y, cada vez más, modelos de IA puedan tomar decisiones sobre ellos. Salió a bolsa en septiembre de 2020 mediante una cotización directa (direct listing), una vía alternativa a la OPV tradicional que evita la ronda de bancos de inversión fijando el precio de salida, algo que solo unas pocas empresas tecnológicas (como Spotify o Slack) habían usado antes.

Desde 2023 ha virado con fuerza hacia el negocio civil y comercial mediante Palantir AIP (Artificial Intelligence Platform), que permite a empresas conectar sus propios datos con modelos de lenguaje de forma controlada, lo que ha disparado tanto sus ingresos como su valoración en bolsa — y también un intenso debate entre inversores sobre si su cotización, a menudo por encima de 50-100 veces sus beneficios en los últimos años, refleja expectativas de crecimiento realistas o es un síntoma más de la fiebre por cualquier empresa que mencione "IA" en su discurso.` },
    'SPCX': { name: 'SpaceX', short: 'SpaceX', icon: '🛰️', color: '#005288', about:
        `SpaceX (Space Exploration Technologies Corp.) fue fundada por Elon Musk en 2002, tras vender PayPal, con el objetivo declarado de reducir drásticamente el coste del acceso al espacio y, a largo plazo, hacer posible la colonización de Marte. Estuvo cerca de la quiebra en 2008, tras tres lanzamientos fallidos consecutivos del cohete Falcon 1 — el cuarto y último intento, con el dinero ya casi agotado, tuvo éxito y salvó a la empresa; ese mismo año la NASA le adjudicó un contrato de reabastecimiento de la Estación Espacial Internacional que resultó clave para su supervivencia.

Desarrolló después los cohetes Falcon 9 y Falcon Heavy, siendo pionera mundial en la reutilización de la primera etapa de los cohetes (aterrizan de forma controlada, vertical, y vuelven a volar en cuestión de semanas), lo que abarató drásticamente el coste por kilo puesto en órbita frente a toda la industria aeroespacial tradicional, donde cada cohete se desechaba tras un solo uso. Opera la cápsula Dragon, que transporta carga y astronautas a la Estación Espacial Internacional para la NASA (siendo la primera empresa privada en llevar astronautas al espacio, en 2020), y Starlink, su red de miles de satélites de internet en órbita baja, que en los últimos años ha pasado de ser un proyecto secundario a representar una parte muy relevante — y creciente — de sus ingresos totales, con aplicaciones que van desde zonas rurales sin cobertura hasta comunicaciones militares. Está desarrollando Starship, el cohete (y nave) más grande y potente jamás construido, íntegramente reutilizable en ambas etapas, pensado tanto para lanzar Starlink a gran escala como para misiones futuras a la Luna (ya seleccionado por la NASA para el programa Artemis) y, eventualmente, Marte.

Tras más de dos décadas como empresa privada —financiada por rondas de capital riesgo y ventas periódicas de acciones en el mercado secundario que llegaron a valorarla en varios cientos de miles de millones de dólares, más que muchas aerolíneas y aeroespaciales cotizadas juntas—, SpaceX salió a bolsa en el Nasdaq bajo el ticker SPCX en junio de 2026, uno de los debuts bursátiles más esperados de la década.` },
    'USPY.DE': { name: 'L&G Cyber Security', short: 'Ciberseguridad', icon: '🔐', color: '#607d8b', about:
        `Gestionado por Legal & General (L&G, aseguradora y gestora británica con más de dos siglos de historia), replica un índice de empresas dedicadas a la ciberseguridad en sentido amplio: protección de redes (firewalls, detección de intrusiones), gestión de identidad y accesos, seguridad en la nube, cifrado de datos y respuesta ante incidentes — desde grandes proveedores establecidos hasta compañías más pequeñas y especializadas en un nicho concreto.

La demanda del sector crece de forma bastante estructural —no solo cíclica— a medida que aumentan los ataques informáticos (ransomware contra hospitales, infraestructuras críticas y administraciones públicas ha sido una tendencia sostenida en los últimos años), el trabajo en remoto amplía la superficie de ataque de las empresas, y la regulación obliga a más sectores a invertir en cumplimiento (el RGPD europeo y normativas sectoriales similares en EE. UU. y Asia). Eso no evita que sus valoraciones suban y bajen con el sentimiento general del sector tecnológico ni que la competencia sea intensa: es un mercado fragmentado con docenas de proveedores especializados, y las grandes tecnológicas (Microsoft, Google) también compiten ofreciendo seguridad integrada en sus propias plataformas en la nube, presionando los márgenes de los especialistas puros.` },
    'IEAA.L': { name: 'iShares Core € Corp Bond', short: 'Bonos Corp.', icon: '🏦', color: '#795548', about:
        `Replica un índice amplio de bonos corporativos denominados en euros con calificación "grado de inversión" (investment grade: empresas consideradas suficientemente solventes por las agencias de rating —Moody's, S&P, Fitch— como para tener bajo riesgo de impago, a diferencia de los bonos "high yield" o "basura", más rentables pero con más riesgo de no cobrar).

Es el activo más conservador y de renta fija de la cartera: en vez de comprar una parte de una empresa (acción, con derecho residual sobre beneficios y sin garantía de devolución), le prestas dinero a cambio de un interés periódico (cupón) fijado de antemano y la devolución del principal a una fecha determinada (vencimiento) — con prioridad de cobro sobre los accionistas si la empresa tuviera problemas.

Su precio se mueve sobre todo por dos factores: las expectativas de tipos de interés del BCE (si los tipos suben, el precio de los bonos ya emitidos con cupones más bajos cae, porque los bonos nuevos pagan más — y viceversa cuando los tipos bajan) y el "diferencial de crédito" (cuánto más pagan estas empresas frente a la deuda pública alemana, considerada el activo más seguro de la eurozona; ese diferencial se amplía cuando el mercado teme una recesión o impagos). Al ser un fondo con muchos emisores distintos y duración media (no todo vencimiento a muy largo plazo), amortigua bastante el riesgo de tipos frente a comprar un solo bono, y sirve sobre todo como colchón de estabilidad frente a la volatilidad de las acciones y las criptomonedas del resto de la cartera — el precio a pagar por esa estabilidad es una rentabilidad esperada mucho menor a largo plazo.` },
};

function getAssetName(ticker) {
    return ASSET_DISPLAY_NAMES[ticker?.toUpperCase()]?.name || null;
}

function getTickerIcon(ticker, type) {
    const info = ASSET_DISPLAY_NAMES[ticker?.toUpperCase()];
    if (info) return info.icon;
    if (type === 'crypto') return '🪙';
    if (type === 'etf') return '📊';
    if (type === 'fund') return '📈';
    return ticker?.substring(0, 2).toUpperCase() || '??';
}

// Utility Functions
function formatCurrency(value, currency = 'EUR') {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

function formatNumber(value, decimals = 2) {
    return new Intl.NumberFormat('es-ES', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

function formatPercent(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${formatNumber(value)}%`;
}

function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('es-ES', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

function formatTime(dateStr) {
    return new Date(dateStr).toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// API Functions
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

async function fetchPortfolio() {
    return fetchAPI('/portfolio');
}

async function fetchHistory(days = 365) {
    return fetchAPI(`/portfolio/history?days=${days}`);
}

async function refreshData() {
    return fetchAPI('/refresh');
}

// UI Update Functions
function updateStatus(online) {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    
    if (dot && text) {
        if (online) {
            dot.className = 'status-dot online';
            text.textContent = 'Conectado';
        } else {
            dot.className = 'status-dot offline';
            text.textContent = 'Sin conexión';
        }
    }
}

function updateLastUpdate(timestamp) {
    const el = document.getElementById('lastUpdate');
    if (el) {
        el.textContent = formatTime(timestamp);
    }
}

function updateSummary(data) {
    // Total Value
    const totalValueEl = document.getElementById('totalValue');
    if (totalValueEl) {
        totalValueEl.innerHTML = formatCurrency(data.total_value, data.base_currency);
    }
    
    // Base Currency
    const baseCurrencyEl = document.getElementById('baseCurrency');
    if (baseCurrencyEl) {
        baseCurrencyEl.textContent = data.base_currency;
    }
    
    // Daily Change
    const dailyEl = document.getElementById('dailyChange');
    if (dailyEl) {
        const dailyClass = data.daily_change >= 0 ? 'positive' : 'negative';
        dailyEl.className = `change-daily ${dailyClass}`;
        dailyEl.innerHTML = `Hoy: ${formatPercent(data.daily_change_pct)} (${formatCurrency(data.daily_change, data.base_currency)})`;
    }
    
    // Total Gain/Loss
    const totalEl = document.getElementById('totalGainLoss');
    if (totalEl) {
        const totalClass = data.total_gain_loss >= 0 ? 'positive' : 'negative';
        totalEl.className = `change-total ${totalClass}`;
        totalEl.innerHTML = `Total: ${formatPercent(data.total_gain_loss_pct)} (${formatCurrency(data.total_gain_loss, data.base_currency)})`;
    }
    
    // Positions count
    const positionsCountEl = document.getElementById('positionsCount');
    if (positionsCountEl) {
        positionsCountEl.textContent = data.positions?.length || 0;
    }
}

function updateKPIs(kpis) {
    // CAGR
    const cagrEl = document.getElementById('cagr');
    if (cagrEl) {
        cagrEl.textContent = kpis.cagr ? `${formatNumber(kpis.cagr)}%` : 'N/A';
        cagrEl.className = `kpi-value ${kpis.cagr >= 0 ? 'positive' : 'negative'}`;
    }
    
    // Max Drawdown
    const ddEl = document.getElementById('maxDrawdown');
    if (ddEl) {
        ddEl.textContent = kpis.max_drawdown ? `-${formatNumber(kpis.max_drawdown)}%` : 'N/A';
        ddEl.className = 'kpi-value negative';
    }
    
    // Volatility
    const volEl = document.getElementById('volatility');
    if (volEl) {
        volEl.textContent = kpis.volatility ? `${formatNumber(kpis.volatility)}%` : 'N/A';
    }
    
    // Sharpe Ratio
    const sharpeEl = document.getElementById('sharpeRatio');
    if (sharpeEl) {
        sharpeEl.textContent = kpis.sharpe_ratio ? formatNumber(kpis.sharpe_ratio) : 'N/A';
        sharpeEl.className = `kpi-value ${kpis.sharpe_ratio >= 1 ? 'positive' : ''}`;
    }
    
    // Best/Worst day for analysis page
    const bestDayEl = document.getElementById('bestDay');
    if (bestDayEl) {
        bestDayEl.textContent = kpis.best_day ? formatPercent(kpis.best_day) : '+0.00%';
    }
    
    const worstDayEl = document.getElementById('worstDay');
    if (worstDayEl) {
        worstDayEl.textContent = kpis.worst_day ? formatPercent(kpis.worst_day) : '-0.00%';
    }

    const positiveDaysEl = document.getElementById('positiveDays');
    if (positiveDaysEl) {
        positiveDaysEl.textContent = kpis.positive_days_pct != null ? `${formatNumber(kpis.positive_days_pct, 1)}%` : '0%';
    }

    const ytdEl = document.getElementById('ytdReturn');
    if (ytdEl) {
        ytdEl.textContent = kpis.ytd_return != null ? formatPercent(kpis.ytd_return) : '0.00%';
        ytdEl.className = `stat-value ${kpis.ytd_return >= 0 ? 'positive' : 'negative'}`;
    }
}

function updateQuickStats(data) {
    if (!data.positions || data.positions.length === 0) return;
    
    // Best performer
    const bestPerformer = data.positions.reduce((best, pos) => 
        pos.gain_loss_pct > (best?.gain_loss_pct || -Infinity) ? pos : best
    , null);
    
    const bestEl = document.getElementById('bestPerformer');
    if (bestEl && bestPerformer) {
        const bestName = getAssetName(bestPerformer.ticker) || bestPerformer.name || bestPerformer.ticker;
        bestEl.innerHTML = `<span style="color: var(--positive)">${bestName}</span> ${formatPercent(bestPerformer.gain_loss_pct)}`;
    }
    
    // Worst performer
    const worstPerformer = data.positions.reduce((worst, pos) => 
        pos.gain_loss_pct < (worst?.gain_loss_pct || Infinity) ? pos : worst
    , null);
    
    const worstEl = document.getElementById('worstPerformer');
    if (worstEl && worstPerformer) {
        const worstName = getAssetName(worstPerformer.ticker) || worstPerformer.name || worstPerformer.ticker;
        worstEl.innerHTML = `<span style="color: var(--negative)">${worstName}</span> ${formatPercent(worstPerformer.gain_loss_pct)}`;
    }
}

function updatePositionsTable(positions) {
    const tbody = document.getElementById('positionsBody');
    if (!tbody) return;
    
    if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="loading-row">No hay posiciones</td></tr>';
        return;
    }
    
    // Apply filters
    const typeFilter = document.getElementById('filterType')?.value || 'all';
    const brokerFilter = document.getElementById('filterBroker')?.value || 'all';
    const searchTerm = document.getElementById('searchPositions')?.value?.toLowerCase() || '';
    
    let filtered = positions;
    if (typeFilter !== 'all') {
        filtered = filtered.filter(p => p.type === typeFilter);
    }
    if (brokerFilter !== 'all') {
        filtered = filtered.filter(p => p.broker === brokerFilter);
    }
    if (searchTerm) {
        filtered = filtered.filter(p => 
            p.ticker.toLowerCase().includes(searchTerm) ||
            (p.name && p.name.toLowerCase().includes(searchTerm))
        );
    }
    
    // Sort
    filtered.sort((a, b) => {
        let aVal = a[sortColumn];
        let bVal = b[sortColumn];
        
        if (typeof aVal === 'string') {
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }
        
        if (sortDirection === 'asc') {
            return aVal > bVal ? 1 : -1;
        }
        return aVal < bVal ? 1 : -1;
    });
    
    tbody.innerHTML = filtered.map(pos => {
        const assetName = getAssetName(pos.ticker) || pos.name || pos.ticker;
        const icon = getTickerIcon(pos.ticker, pos.type);
        const typeName = {'crypto': 'Crypto', 'etf': 'ETF', 'fund': 'Fondo', 'stock': 'Acción'}[pos.type] || pos.type;
        
        return `
        <tr onclick="showAssetDetail('${pos.ticker}')" style="cursor:pointer" title="Ver detalle de ${assetName}">
            <td>
                <div class="ticker-cell">
                    <div class="ticker-icon">${icon}</div>
                    <div class="ticker-info">
                        <span class="ticker-symbol">${assetName}</span>
                        <span class="ticker-name">${pos.ticker}</span>
                    </div>
                </div>
            </td>
            <td><span class="type-badge ${pos.type}">${typeName}</span></td>
            <td><span class="broker-name">${pos.broker}</span></td>
            <td class="text-right mono">${formatNumber(pos.quantity, pos.type === 'crypto' ? 6 : 2)}</td>
            <td class="text-right mono">${formatNumber(pos.avg_price)}</td>
            <td class="text-right mono">${formatNumber(pos.current_price)}</td>
            <td class="text-right mono">${formatCurrency(pos.market_value, pos.currency)}</td>
            <td class="text-right mono ${pos.gain_loss >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatCurrency(pos.gain_loss, pos.currency)}
            </td>
            <td class="text-right mono ${pos.gain_loss_pct >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatPercent(pos.gain_loss_pct)}
            </td>
            <td class="text-right mono ${pos.day_change_pct >= 0 ? 'value-positive' : 'value-negative'}">
                ${formatPercent(pos.day_change_pct)}
            </td>
            <td class="text-right mono">${formatNumber(pos.weight)}%</td>
        </tr>
    `}).join('');
}

function updateBrokerFilter(brokers) {
    const select = document.getElementById('filterBroker');
    if (!select) return;
    
    const currentValue = select.value;
    
    select.innerHTML = '<option value="all">Todos los brokers</option>' +
        Object.keys(brokers).map(broker => 
            `<option value="${broker}">${broker}</option>`
        ).join('');
    
    select.value = currentValue;
}

function updateTopMovers(positions) {
    const container = document.getElementById('topMovers');
    if (!container || !positions) return;
    
    const sorted = [...positions].sort((a, b) => Math.abs(b.day_change_pct) - Math.abs(a.day_change_pct));
    const topMovers = sorted.slice(0, 5);
    
    container.innerHTML = topMovers.map(pos => `
        <div class="mover-item" style="display: flex; justify-content: space-between; padding: 10px; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 8px;">
            <span style="font-family: var(--font-mono); font-weight: 600;">${pos.ticker}</span>
            <span class="${pos.day_change_pct >= 0 ? 'value-positive' : 'value-negative'}" style="font-family: var(--font-mono);">
                ${formatPercent(pos.day_change_pct)}
            </span>
        </div>
    `).join('');
}

// Chart Functions
function createPortfolioChart(history) {
    const ctx = document.getElementById('portfolioChart');
    if (!ctx) return;
    
    if (charts.portfolio && typeof charts.portfolio.destroy === 'function') {
        charts.portfolio.destroy();
    }
    
    // Filter by period
    let filteredHistory = history;
    if (currentPeriod !== 'all') {
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - currentPeriod);
        filteredHistory = history.filter(h => new Date(h.date) >= cutoff);
    }
    
    const labels = filteredHistory.map(h => h.date);
    const values = filteredHistory.map(h => h.value);
    
    // Calculate gradient
    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 350);
    gradient.addColorStop(0, 'rgba(0, 212, 170, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 212, 170, 0)');
    
    charts.portfolio = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Valor de Cartera',
                data: values,
                borderColor: '#00d4aa',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#00d4aa',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1a2332',
                    titleColor: '#94a3b8',
                    bodyColor: '#f8fafc',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: function(context) {
                            return formatDate(context[0].label);
                        },
                        label: function(context) {
                            return formatCurrency(context.raw, 'EUR');
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#64748b',
                        maxTicksLimit: 8,
                        callback: function(value, index) {
                            const date = new Date(this.getLabelForValue(value));
                            return date.toLocaleDateString('es-ES', { month: 'short', day: 'numeric' });
                        }
                    }
                },
                y: {
                    grid: {
                        color: '#1e293b'
                    },
                    ticks: {
                        color: '#64748b',
                        callback: function(value) {
                            return formatCurrency(value, 'EUR');
                        }
                    }
                }
            }
        }
    });
}

function createDoughnutChart(canvasId, data, legendId) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    const chartKey = canvasId.replace('Chart', '');
    if (charts[chartKey] && typeof charts[chartKey].destroy === 'function') {
        charts[chartKey].destroy();
    }
    
    const labels = Object.keys(data);
    const values = labels.map(k => data[k].value || data[k].weight);
    const weights = labels.map(k => data[k].weight);
    
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: CONFIG.CHART_COLORS.slice(0, labels.length),
                borderColor: '#151d2c',
                borderWidth: 3,
                hoverBorderColor: '#1a253a',
                hoverBorderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1a2332',
                    titleColor: '#94a3b8',
                    bodyColor: '#f8fafc',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const weight = weights[context.dataIndex];
                            return `${weight}%`;
                        }
                    }
                }
            }
        }
    });
    
    charts[chartKey] = chart;
    
    // Update legend
    const legendEl = document.getElementById(legendId);
    if (legendEl) {
        legendEl.innerHTML = labels.map((label, i) => `
            <div class="legend-item">
                <span class="legend-color" style="background: ${CONFIG.CHART_COLORS[i]}"></span>
                <span class="legend-label">${label}</span>
                <span class="legend-value">${formatNumber(weights[i])}%</span>
            </div>
        `).join('');
    }
}

// Export to CSV
function exportToCSV() {
    if (!portfolioData || !portfolioData.positions) return;
    
    const headers = ['Ticker', 'Nombre', 'Tipo', 'Broker', 'Cantidad', 'Precio Medio', 'Precio Actual', 'Valor', 'P/L', 'P/L %', 'Peso %'];
    const rows = portfolioData.positions.map(p => [
        p.ticker,
        p.name,
        p.type,
        p.broker,
        p.quantity,
        p.avg_price,
        p.current_price,
        p.market_value,
        p.gain_loss,
        p.gain_loss_pct,
        p.weight
    ]);
    
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `portfolio_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    
    URL.revokeObjectURL(url);
    
    if (window.showToast) {
        window.showToast('CSV exportado correctamente', 'success');
    }
}

// Check which backend integrations are configured and surface a banner if any are missing.
async function loadIntegrationsStatus() {
    const banner = document.getElementById('integrationsBanner');
    if (!banner) return;
    try {
        const status = await fetchAPI('').catch(() => null) || await (await fetch(`${CONFIG.API_BASE_URL}`)).json();
        const checks = [
            { key: 'has_gemini', label: 'Gemini (briefing diario + FinBot)', env: 'GEMINI_API_KEY' },
            { key: 'has_kraken', label: 'Kraken (sync cripto cada 15 min)', env: 'KRAKEN_API_KEY + KRAKEN_API_SECRET' },
            { key: 'has_telegram', label: 'Telegram (alertas push)', env: 'TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID' },
        ];
        const missing = checks.filter(c => !status[c.key]);
        if (missing.length === 0) {
            banner.style.display = 'none';
            return;
        }
        const items = missing.map(m =>
            `<li><strong>${m.label}</strong> — define <code>${m.env}</code> en Render → Environment</li>`
        ).join('');
        banner.innerHTML = `
            <div class="integrations-banner-inner">
                <div class="integrations-banner-icon">⚙️</div>
                <div class="integrations-banner-body">
                    <strong>Quedan ${missing.length} integraci${missing.length === 1 ? 'ón' : 'ones'} por activar</strong>
                    <ul>${items}</ul>
                    <small>Lo que ya funciona: portfolio, posiciones, news, charts y FinBot con Groq.</small>
                </div>
            </div>
        `;
        banner.style.display = 'block';
    } catch (err) {
        console.warn('Could not load integrations status:', err);
    }
}

// Main Functions
async function loadDashboard() {
    try {
        updateStatus(false);

        loadIntegrationsStatus();

        // Fetch portfolio data
        portfolioData = await fetchPortfolio();
        
        // Update UI
        updateSummary(portfolioData);
        updateKPIs(portfolioData.kpis);
        updateQuickStats(portfolioData);
        updatePositionsTable(portfolioData.positions);
        updateBrokerFilter(portfolioData.by_broker);
        updateLastUpdate(portfolioData.last_updated);
        updateTopMovers(portfolioData.positions);
        
        // Create distribution charts
        if (portfolioData.by_type && Object.keys(portfolioData.by_type).length > 0) {
            createDoughnutChart('typeChart', portfolioData.by_type, 'typeLegend');
        }
        if (portfolioData.by_broker && Object.keys(portfolioData.by_broker).length > 0) {
            createDoughnutChart('brokerChart', portfolioData.by_broker, 'brokerLegend');
        }
        if (portfolioData.by_currency && Object.keys(portfolioData.by_currency).length > 0) {
            createDoughnutChart('currencyChart', portfolioData.by_currency, 'currencyLegend');
        }
        
        // Fetch and create history chart
        const historyData = await fetchHistory(365);
        if (historyData.history && historyData.history.length > 0) {
            createPortfolioChart(historyData.history);
        }
        
        updateStatus(true);
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        updateStatus(false);
        
        // Show error state
        const totalValueEl = document.getElementById('totalValue');
        if (totalValueEl) {
            totalValueEl.innerHTML = '<span class="value-loading">Error al cargar datos</span>';
        }
    }
}

async function handleRefresh() {
    const btn = document.getElementById('btnRefresh');
    const overlay = document.getElementById('loadingOverlay');
    
    if (btn) btn.classList.add('loading');
    if (overlay) overlay.classList.add('active');
    
    try {
        await refreshData();
        await loadDashboard();
        if (window.showToast) {
            window.showToast('Datos actualizados correctamente', 'success');
        }
    } catch (error) {
        console.error('Error refreshing:', error);
        if (window.showToast) {
            window.showToast('Error al actualizar datos', 'error');
        }
    } finally {
        if (btn) btn.classList.remove('loading');
        if (overlay) overlay.classList.remove('active');
    }
}

function handlePeriodChange(period) {
    currentPeriod = period === 'all' ? 'all' : parseInt(period);
    
    // Update active button
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === String(period));
    });
    
    // Reload history chart
    if (portfolioData) {
        fetchHistory(period === 'all' ? 3650 : 365).then(data => {
            if (data.history) {
                createPortfolioChart(data.history);
            }
        });
    }
}

function handleFilterChange() {
    if (portfolioData) {
        updatePositionsTable(portfolioData.positions);
    }
}

function handleSort(column) {
    if (sortColumn === column) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = column;
        sortDirection = 'desc';
    }
    
    if (portfolioData) {
        updatePositionsTable(portfolioData.positions);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    loadDashboard();
    
    // Refresh button
    const btnRefresh = document.getElementById('btnRefresh');
    if (btnRefresh) {
        btnRefresh.addEventListener('click', handleRefresh);
    }
    
    // Period buttons
    document.querySelectorAll('.chart-btn').forEach(btn => {
        btn.addEventListener('click', () => handlePeriodChange(btn.dataset.period));
    });
    
    // Filters
    const filterType = document.getElementById('filterType');
    const filterBroker = document.getElementById('filterBroker');
    const searchPositions = document.getElementById('searchPositions');
    
    if (filterType) filterType.addEventListener('change', handleFilterChange);
    if (filterBroker) filterBroker.addEventListener('change', handleFilterChange);
    if (searchPositions) searchPositions.addEventListener('input', handleFilterChange);
    
    // Table sorting
    document.querySelectorAll('.positions-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => handleSort(th.dataset.sort));
    });
    
    // Export CSV
    const btnExport = document.getElementById('btnExportCSV');
    if (btnExport) {
        btnExport.addEventListener('click', exportToCSV);
    }
    
    // Auto-refresh every minute
    setInterval(loadDashboard, CONFIG.REFRESH_INTERVAL);
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Press 'R' to refresh
    if ((e.key === 'r' || e.key === 'R') && !e.ctrlKey && !e.metaKey) {
        const activeElement = document.activeElement;
        if (activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA') {
            handleRefresh();
        }
    }
});
