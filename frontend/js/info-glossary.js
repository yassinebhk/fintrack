/**
 * Info-icon glossary — a small "i" next to any metric/chart label that, on
 * click, explains what it is, how it's used, and how to read its value.
 * Every page script calls `infoIcon('key')` inside its template literals;
 * this file owns the glossary content and the single shared popover.
 *
 * Wording for terms that already exist in the full A-Z glossary
 * (frontend/js/pages.js, #glosario section of "Aprender") is kept consistent
 * with that page rather than reinvented, so the same term reads the same
 * way everywhere in the app.
 */

const INFO_GLOSSARY = {
    // ---------- Valuation (stocks) ----------
    per: {
        title: 'PER (P/E)',
        what: 'Precio dividido entre beneficio por acción: cuántos años de beneficios actuales "pagas" al comprar la acción a su precio de hoy.',
        read: 'Más bajo = más barata en apariencia, pero SOLO es comparable dentro del mismo sector — un banco y una tecnológica tienen PER "normales" muy distintos.',
    },
    peg: {
        title: 'PEG',
        what: 'El PER dividido entre el crecimiento esperado de beneficios — ajusta lo "cara" que está una acción por lo que realmente crece.',
        read: 'Un PEG en torno a 1 se considera razonable. Por debajo de 1, la acción puede estar barata para lo que crece; muy por encima, cara incluso si el PER a secas parecía normal.',
    },
    pb: {
        title: 'P/B (precio/valor contable)',
        what: 'El precio de la acción comparado con el valor contable (patrimonio neto) de la empresa por acción.',
        read: 'Un P/B de 1 significa que pagas justo lo que "vale en libros" la empresa. Por debajo de 1 puede ser ganga o señal de mal negocio; combínalo siempre con el ROE antes de sacar conclusiones.',
    },
    roe: {
        title: 'ROE (rentabilidad sobre recursos propios)',
        what: 'El beneficio que genera una empresa por cada euro de capital que han puesto sus accionistas.',
        read: 'Más alto = negocio más rentable/eficiente. Es el termómetro principal de "calidad de negocio" — distingue "barato porque es ganga" de "barato porque es mal negocio".',
    },
    dividend_yield: {
        title: 'Yield (rentabilidad por dividendo)',
        what: 'El dividendo anual que paga la empresa dividido entre el precio actual de la acción, en %.',
        read: 'Yields muy altos (8-10%+) a veces anticipan un recorte de dividendo. Yields moderados (2-5%) y estables en el tiempo suelen ser más fiables.',
    },
    debt_ratio: {
        title: 'Deuda (endeudamiento)',
        what: 'Cuánta deuda tiene la empresa en relación con sus activos, su patrimonio o su beneficio, según el ratio mostrado.',
        read: 'Más bajo = más solidez financiera, aguanta mejor una crisis o subida de tipos. Muy alto no es automáticamente malo, pero añade riesgo si el negocio se tuerce.',
    },

    // ---------- Risk & performance ----------
    margen: {
        title: 'Margen',
        what: 'El porcentaje de las ventas que la empresa se queda como beneficio, después de todos sus costes.',
        read: 'Más alto = negocio más rentable por cada euro que factura. Compáralo dentro del mismo sector: un margen "normal" varía mucho entre, p.ej., un supermercado y un fabricante de software.',
    },
    crec_ventas: {
        title: 'Crec. ventas',
        what: 'Cuánto han crecido las ventas de la empresa frente al año anterior.',
        read: 'Crecimiento sostenido en el tiempo es más valioso que un salto puntual — revisa si se mantiene varios años seguidos, no solo el último dato.',
    },
    yield_bono: {
        title: 'Yield (bono/ETF de bonos)',
        what: 'El interés anual que reparte el fondo de bonos, en %.',
        read: 'Más alto suele ir de la mano de más riesgo (plazos más largos o emisores menos solventes) — no lo mires aislado del "Yield real" ni de la duración.',
    },
    yield_real: {
        title: 'Yield real',
        what: 'El yield menos la inflación implícita del mercado — lo que de verdad ganas por encima de la inflación.',
        read: 'Un yield del 4% con inflación del 3% son solo 1% real. Si el yield real es negativo, tu dinero pierde poder adquisitivo aunque cobres intereses.',
    },
    duracion_bono: {
        title: 'Duración',
        what: 'Cuánto tarda de media en devolverte el dinero un bono/ETF de bonos — a más larga, más sensible es su precio a cambios de tipos de interés.',
        read: 'Duración corta = precio más estable pero menos yield habitualmente. Duración larga = más potencial de ganancia (o pérdida) si los tipos bajan (o suben).',
    },
    sensib_tipos: {
        title: 'Sensib. tipos (beta de tipos)',
        what: 'Cuánto se mueve el precio del bono/ETF cuando cambian los tipos de interés de referencia.',
        read: 'Un valor más alto significa mayor impacto (positivo si los tipos bajan, negativo si suben) — relacionado directamente con la duración.',
    },
    momentum_criterio: {
        title: 'Momentum (tendencia)',
        what: 'Uno de los "jueces" del motor cuantitativo: mide la fuerza de la tendencia reciente del activo — lo que ha subido de forma sostenida tiende a seguir subiendo a medio plazo.',
        read: 'Puntuación positiva y alta = tendencia fuerte al alza que este juez considera que puede continuar. Es una de las dos grandes tesis del motor (frente a valor/contrarian).',
    },
    tecnico_rsi_macd: {
        title: 'Técnico (RSI/MACD)',
        what: 'Uno de los "jueces" del motor: combina indicadores técnicos clásicos (RSI para sobrecompra/sobreventa, MACD para cambios de tendencia) en una única señal.',
        read: 'Puntuación alta = las señales técnicas de corto plazo apoyan la tesis. Son indicadores de corto plazo, más útiles para el timing que para decidir SI invertir a largo plazo.',
    },
    infravaloracion_criterio: {
        title: 'Infravaloración',
        what: 'Uno de los "jueces" del motor: puntúa si el activo parece barato frente a sus fundamentales (PER, P/B) o su propia historia de precios reciente.',
        read: 'Puntuación alta = parece infravalorado según este criterio — apoya la tesis de valor/contrarian, la contraria al momentum.',
    },
    reversion_media: {
        title: 'Reversión a la media',
        what: 'Uno de los "jueces" del motor: la tendencia de un precio muy alejado de su media histórica a "volver" hacia ella con el tiempo.',
        read: 'Puntuación alta = el activo está inusualmente lejos de su media reciente, lo que este juez interpreta como una probabilidad mayor de corrección hacia ese promedio.',
    },
    riesgo_score: {
        title: 'Riesgo (puntuación compuesta)',
        what: 'Combina varias señales (volatilidad, caídas históricas, concentración, deuda...) en un único número para comparar activos de un vistazo.',
        read: 'Más alto = movimientos más bruscos (pasados o esperados). No es "malo" en sí — solo debe encajar con cuánto aguantas ver caer tu inversión sin vender por pánico.',
    },
    max_drawdown: {
        title: 'Drawdown / Máx. Drawdown',
        what: 'La peor caída porcentual desde el punto más alto alcanzado, no desde que empezaste a invertir. Mide el "dolor" máximo real sufrido.',
        read: 'Un -40% significa que, en el peor momento, la inversión llegó a valer un 40% menos que su máximo histórico. Cuanto más negativo, más paciencia y horizonte necesitas para no vender en el peor momento.',
    },
    drawdown_historico: {
        title: 'Gráfico de drawdown histórico',
        what: 'Para cada día del pasado, cuánto por debajo estaba el valor respecto a su máximo histórico hasta ese momento (siempre ≤ 0%).',
        read: 'Cuanto más tiempo pasa la línea pegada a 0%, mejor (hace máximos nuevos a menudo). Valles anchos y profundos indican rachas largas y duras en pérdidas, aunque se acabase recuperando.',
    },
    cvar95: {
        title: 'CVaR 95% (Expected Shortfall)',
        what: 'De los peores 5% de días (1 de cada 20), la pérdida MEDIA de esos días malos — no la peor de todas, el promedio de la "cola mala".',
        read: 'Cuanto menos negativo, mejor. Un -3,5% significa que en el peor 5% de días, de media se perdió un 3,5%. Úsalo para dimensionar el peor escenario plausible, no solo un día cualquiera.',
    },
    alfa_anual: {
        title: 'Alpha (alfa anual)',
        what: 'El retorno de más (o de menos) que obtuvo una estrategia/activo frente a lo que le correspondía por el riesgo de mercado asumido, comparado con un benchmark.',
        read: 'Positivo = ha añadido valor por encima de simplemente seguir al mercado. Cercano a 0 o negativo = no aporta nada que no diera ya el mercado, o incluso resta.',
    },
    regimen_200d: {
        title: 'Régimen de mercado (breadth, sobre 200d)',
        what: '% de un universo amplio de activos que cotiza por encima de su media móvil de 200 sesiones (~1 año) — mide si el mercado en general está alcista o bajista.',
        read: 'Por encima de ~55-60% se considera alcista (favorece momentum); por debajo de ~40-45%, bajista (favorece valor/defensivo). Cambia qué señales son más fiables ahora mismo.',
    },
    distribucion_retornos: {
        title: 'Distribución de retornos diarios',
        what: 'Histograma que agrupa los retornos diarios históricos por rangos y muestra cuántos días cayeron en cada uno.',
        read: 'Una campana estrecha y centrada en positivo es lo deseable. Colas largas hacia la izquierda avisan de días de caída severa poco frecuentes pero posibles.',
    },
    correlacion: {
        title: 'Correlación de activos',
        what: 'Cuánto tienden a moverse dos activos en la misma dirección. Va de -1 (siempre en direcciones opuestas) a +1 (siempre en la misma dirección); 0 significa que no hay relación aparente.',
        read: 'Correlaciones altas (+0,7 o más) entre tus posiciones significan que, aunque tengas muchos activos, en la práctica están poco diversificados — si uno cae, es probable que los demás también. Buscar activos con correlación baja o negativa entre sí reduce el riesgo del conjunto.',
    },
    riesgo_retorno_scatter: {
        title: 'Riesgo / Retorno (scatter)',
        what: 'Cada punto es un activo de tu cartera: en el eje X su volatilidad reciente, en el eje Y su retorno reciente. El tamaño del punto refleja su peso en la cartera.',
        read: 'Los mejores activos están arriba-a-la-izquierda (ganan mucho moviéndose poco); los peores, abajo-a-la-derecha (pierden moviéndose mucho). Útil para ver de un vistazo qué posiciones "no compensan" el riesgo que asumen.',
    },
    retornos_mensuales: {
        title: 'Retornos mensuales (mapa de calor)',
        what: 'El rendimiento de tu cartera en cada mes individual, coloreado en verde (positivo) o rojo (negativo).',
        read: 'Sirve para detectar estacionalidad (¿siempre te va peor en un mes concreto?) y rachas — varios meses rojos seguidos son más informativos que un solo mal mes aislado.',
    },
    rolling_vol_sharpe: {
        title: 'Volatilidad y Sharpe móviles (30d)',
        what: 'Cómo han ido cambiando tu volatilidad y tu Sharpe (retorno ajustado a riesgo) calculados en ventanas móviles de 30 días, en vez de un único número para todo el periodo.',
        read: 'Te permite ver si el riesgo de tu cartera ha ido subiendo o bajando con el tiempo, en vez de solo conocer el promedio histórico — una subida sostenida de volatilidad puede avisar de un cambio de régimen antes de que se note en el resultado.',
    },
    sharpe: {
        title: 'Sharpe (ratio)',
        what: 'Retorno obtenido por encima del activo sin riesgo, dividido entre la volatilidad asumida para conseguirlo.',
        read: 'Por debajo de 0,5 se considera pobre, 1 razonable, por encima de 1,5-2 muy bueno (y con pocos datos, sospechoso de sobreajuste).',
    },
    sortino: {
        title: 'Sortino (ratio)',
        what: 'Como el Sharpe, pero solo penaliza la volatilidad a la baja — subir a saltos no se considera "malo" aquí.',
        read: 'Se interpreta igual que Sharpe (más alto mejor) pero suele salir algo más alto para el mismo activo, al ser más justo con subidas bruscas.',
    },
    volatilidad: {
        title: 'Volatilidad anualizada',
        what: 'Cuánto oscila el valor de una inversión de un día/mes a otro, expresado en términos de un año completo.',
        read: '10-15% anual es típico de una cartera diversificada; 30%+ es propio de acciones individuales o cripto — significa oscilaciones grandes en ambos sentidos en un año cualquiera.',
    },
    beta: {
        title: 'Beta',
        what: 'Cuánto se mueve un activo en promedio cuando el mercado de referencia se mueve un 1%.',
        read: 'Beta 1,5 amplifica un 50% los movimientos del mercado; beta 0,5 los amortigua a la mitad. No dice si el activo es "bueno", solo cuánto amplifica.',
    },
    cagr: {
        title: 'CAGR (crecimiento anual compuesto)',
        what: 'La tasa de crecimiento anual constante que, aplicada todo el periodo, habría dado el mismo resultado final que el rendimiento real con sus altibajos.',
        read: 'Un CAGR del 7% en 10 años significa un crecimiento medio compuesto del 7% anual, aunque algunos años fueran mucho mejores o peores que ese promedio.',
    },
    calmar: {
        title: 'Ratio de Calmar',
        what: 'Compara la rentabilidad anual con la peor caída sufrida (Max Drawdown): rentabilidad anual ÷ máxima caída.',
        read: 'Responde a "¿cuánto gano por cada punto de dolor máximo que aguanto?". Más alto es mejor; por debajo de 0,5 suele considerarse flojo para el riesgo asumido.',
    },
    anos_cubiertos: {
        title: 'Años cubiertos',
        what: 'Cuántos años de histórico de precios se han usado para calcular todas estas métricas.',
        read: 'Cuantos más años, más fiables son las estadísticas — con muy pocos años (1-2), cualquier ratio puede estar dominado por un único evento puntual (una buena o mala racha) en vez de reflejar el comportamiento típico del activo.',
    },
    drawdown_duracion_max: {
        title: 'Duración máx. (días) de drawdown',
        what: 'Cuántos días duró, de principio a fin, la peor racha de caída-y-recuperación del activo (desde que tocó máximos hasta que los recuperó).',
        read: 'Cuanto más largo, más paciencia hizo falta para no vender en el peor momento y esperar a recuperar lo perdido — es una medida de "cuánto tiempo puede doler", no solo de "cuánto".',
    },
    drawdown_duracion_media: {
        title: 'Duración media (días) de drawdown',
        what: 'El tiempo medio que tarda el activo en recuperar un máximo después de una caída, promediando todas las caídas históricas (no solo la peor).',
        read: 'Da una idea de "lo normal" para este activo, más allá del peor caso puntual — útil para calibrar expectativas realistas sobre cuánto tiempo puede pasar en pérdidas.',
    },
    var95: {
        title: 'VaR 95% diario',
        what: 'La pérdida diaria que, según el histórico, solo se supera 1 de cada 20 días (el 5% peor de los días).',
        read: 'Es el umbral de un "mal día típico", no el peor caso posible — para eso está el CVaR, que sí mide la media de esos días malos en vez de solo el umbral.',
    },
    var99: {
        title: 'VaR 99% diario',
        what: 'La pérdida diaria que solo se supera 1 de cada 100 días — un umbral más exigente y raro que el VaR 95%.',
        read: 'Compáralo con el VaR 95%: si la diferencia entre ambos es grande, significa que el activo tiene una cola de riesgo más pronunciada de lo que parece a simple vista.',
    },
    cvar99: {
        title: 'CVaR 99% (Expected Shortfall)',
        what: 'De los peores días extremos (el 1% más raro, uno de cada 100), la pérdida media de esos días — el escenario de "cisne negro" más que el de un mal día normal.',
        read: 'Al fijarse en un evento más raro que el CVaR 95%, este número suele ser bastante más negativo — la diferencia entre ambos indica cuánto se dispara el riesgo en los escenarios más extremos.',
    },
    skewness: {
        title: 'Asimetría (skew)',
        what: 'Si los retornos diarios se reparten de forma simétrica alrededor de la media, o si tienen una "cola" más larga hacia un lado.',
        read: 'Skew negativo = ocasionales caídas fuertes con subidas más frecuentes pero pequeñas (típico de acciones). Skew positivo = lo contrario. Cuanto más se aleje de 0, más asimétrico es el riesgo real frente a lo que sugiere solo la volatilidad.',
    },
    excess_kurtosis: {
        title: 'Curtosis exceso',
        what: 'Cuántos días "extremos" (muy buenos o muy malos) hay comparado con lo que predeciría una distribución normal (campana de Gauss).',
        read: 'Positivo = más días extremos de lo "normal" (colas gordas) — la volatilidad media puede infravalorar el riesgo real de sustos puntuales. Cerca de 0 = se comporta de forma más parecida a lo esperado estadísticamente.',
    },
    jarque_bera: {
        title: 'Jarque-Bera (p)',
        what: 'Un test estadístico que comprueba si los retornos diarios siguen (aproximadamente) una distribución normal, combinando la asimetría y la curtosis en un único p-valor.',
        read: 'p por debajo de 0,05 indica que los retornos NO son normales (hay asimetría o colas gordas reales) — una señal de que los modelos que asumen normalidad (como el VaR clásico) pueden subestimar el riesgo de este activo en concreto.',
    },
    alpha_t_stat: {
        title: 't-stat del alfa',
        what: 'Mide si el alfa observado es lo bastante grande, en relación a su variabilidad, como para no ser simple azar estadístico.',
        read: 'Como referencia rápida, un t-stat con valor absoluto por encima de ~2 (y su p-valor asociado por debajo de 0,05) se considera una señal razonablemente sólida de que el alfa es real y no ruido.',
    },
    r_squared: {
        title: 'R² frente al benchmark',
        what: 'Qué porcentaje de los movimientos de este activo se explica simplemente por los movimientos del benchmark de referencia.',
        read: 'R² alto (80%+) significa que el activo se mueve casi en bloque con su benchmark — el alfa/beta que calcules serán más fiables. R² bajo significa que el activo tiene una dinámica bastante independiente del benchmark elegido, y compararlo con él tiene menos sentido.',
    },
    information_ratio: {
        title: 'Information Ratio',
        what: 'El alfa (exceso de retorno sobre el benchmark) dividido entre lo errático que es ese exceso (tracking error). Es al "batir al índice" lo que el Sharpe es al retorno absoluto.',
        read: 'Más alto es mejor — bate al benchmark de forma consistente, no solo con un año suerte. Por encima de 0,5 se considera decente, por encima de 1, muy bueno.',
    },
    tracking_error: {
        title: 'Tracking error',
        what: 'Cuánto se desvía, típicamente, el retorno de este activo del retorno de su benchmark — su "distancia" respecto al índice de referencia.',
        read: 'Bajo = se comporta casi como un fondo indexado al benchmark. Alto = tiene una gestión/comportamiento muy distinto del índice, para bien o para mal — revisa el alfa junto a esto para saber si esa diferencia ha compensado.',
    },
    treynor: {
        title: 'Ratio de Treynor',
        what: 'El retorno por encima del activo sin riesgo, dividido entre la beta (en vez de entre la volatilidad total, como hace el Sharpe).',
        read: 'Útil cuando comparas activos ya diversificados dentro de una cartera más grande, donde solo importa el riesgo de mercado (beta) que aportan, no su volatilidad en solitario.',
    },
    up_capture: {
        title: 'Up-capture',
        what: 'Qué porcentaje de las subidas del benchmark "captura" este activo cuando el mercado sube.',
        read: 'Por encima de 100% = sube más que el mercado en los buenos momentos (amplifica al alza). Por debajo de 100% = participa solo parcialmente de las subidas.',
    },
    down_capture: {
        title: 'Down-capture',
        what: 'Qué porcentaje de las caídas del benchmark "sufre" este activo cuando el mercado baja.',
        read: 'Por debajo de 100% = cae menos que el mercado en los malos momentos (protege parcialmente). Por encima de 100% = amplifica también las caídas. El perfil ideal es up-capture alto y down-capture bajo.',
    },
    chart_precio_sma: {
        title: 'Precio con SMA50 y SMA200',
        what: 'El precio histórico del activo junto a dos medias móviles: la de 50 sesiones (~2,5 meses, más reactiva) y la de 200 sesiones (~1 año, más lenta), usadas para juzgar la tendencia de fondo.',
        read: 'Precio por encima de ambas medias = tendencia alcista de fondo. El cruce de la SMA50 por encima de la SMA200 ("cruce dorado") es una señal alcista clásica; el cruce contrario ("cruce de la muerte"), bajista.',
    },
    chart_rolling_vol: {
        title: 'Volatilidad rodante 60d',
        what: 'Cómo ha ido cambiando la volatilidad del activo calculada en ventanas móviles de 60 sesiones, en vez de un único número para todo el histórico.',
        read: 'Picos indican periodos de nerviosismo/incertidumbre en el mercado o específicos del activo. Si la volatilidad reciente es mucho más alta que la histórica media, el riesgo "ahora mismo" es mayor de lo que sugiere el resumen a largo plazo.',
    },
    chart_rolling_sharpe: {
        title: 'Sharpe rodante 60d',
        what: 'Cómo ha ido cambiando el Sharpe ratio del activo calculado en ventanas móviles de 60 sesiones.',
        read: 'Un Sharpe rodante que se mantiene positivo de forma consistente es más tranquilizador que un Sharpe medio alto conseguido gracias a un único periodo excepcional.',
    },
    chart_relative_benchmark: {
        title: 'Rendimiento vs benchmark',
        what: 'La evolución del activo comparada directamente con la de su benchmark de referencia, normalizadas para partir del mismo punto.',
        read: 'Si la línea del activo se aleja hacia arriba de la del benchmark, lo está batiendo; si se aleja hacia abajo, se está quedando por detrás — visualiza de un vistazo lo que el alfa resume en un número.',
    },
    momentum_score: {
        title: 'Score momentum',
        what: 'Puntuación del motor cuantitativo que mide la fuerza de la tendencia reciente del activo — cuánto ha subido de forma sostenida.',
        read: 'Positivo y alto = tendencia fuerte al alza reciente (tesis momentum). Negativo = tendencia bajista. Es una de las dos tesis que usa el motor para puntuar oportunidades, junto al score de valor.',
    },
    value_score: {
        title: 'Score valor',
        what: 'Puntuación del motor cuantitativo que mide si el activo parece infravalorado frente a sus fundamentales o su propia historia reciente.',
        read: 'Positivo y alto = parece barato/atractivo por valoración (tesis contrarian/valor). Se combina con el score momentum para decidir qué tesis domina en cada oportunidad.',
    },
    winner_affinity: {
        title: 'Afinidad con el "perfil ganador"',
        what: 'Cuánto se parece este activo, en sus características actuales, a los activos que en el pasado resultaron ser las mejores recomendaciones del motor (según el scorecard histórico).',
        read: 'Más alto = encaja mejor con el patrón de las recomendaciones que salieron bien anteriormente. No es una garantía de que vaya a repetirse, solo una similitud estadística con lo que funcionó antes.',
    },
    return_total: {
        title: 'Return total',
        what: 'La rentabilidad acumulada de todo el periodo, en %, sin anualizar.',
        read: 'Compárala siempre con el CAGR (sí anualizado) y con los años cubiertos: un +50% en 10 años es mucho más flojo que un +50% en 2 años.',
    },
    valor_final: {
        title: 'Valor final',
        what: 'El dinero que tendrías al final del periodo simulado, incluyendo lo invertido más (o menos) las ganancias/pérdidas.',
        read: 'Compáralo siempre con lo realmente invertido — un valor final grande con aportaciones también grandes puede esconder una rentabilidad mediocre.',
    },
    p_value: {
        title: 'p-valor',
        what: 'La probabilidad de que un resultado se deba a pura casualidad, si la estrategia no tuviera realmente ninguna ventaja.',
        read: 'Por debajo de 0,05-0,10 se considera un indicio razonable de que no es azar. Por encima, el resultado es compatible con la suerte y no debería usarse como base para invertir dinero real.',
    },
    psr: {
        title: 'PSR (Probabilistic Sharpe Ratio)',
        what: 'La confianza (en %) de que un Sharpe medido sea real y no un golpe de suerte, dado cuánto tiempo se ha observado.',
        read: '≥95% (a veces se usa 75% como umbral más laxo) se considera razonablemente fiable. El mismo Sharpe con pocos datos puede tener PSR bajo — el tiempo observado importa tanto como el número.',
    },
    oos: {
        title: 'OOS (fuera de muestra)',
        what: 'Resultados medidos sobre datos que la estrategia NO usó para ajustarse, a diferencia del backtest "in-sample" que puede estar sobreajustado.',
        read: 'Un rendimiento OOS mucho peor que el in-sample es señal de sobreajuste. Uno similar es una señal de fiabilidad mucho más fuerte.',
    },
    expectancy: {
        title: 'Expectancy (esperanza matemática)',
        what: 'Ganancia media esperada de una estrategia = (% acierto × ganancia media) + (% fallo × pérdida media).',
        read: 'Puede ser positiva acertando menos del 50% de las veces, si lo que se gana cuando acierta es mayor que lo que se pierde cuando falla. Mira siempre junto al hit rate y el tamaño de la muestra.',
    },
    operaciones_cerradas: {
        title: 'Operaciones cerradas',
        what: 'Cuántas operaciones de papel del diario de trading ya se han cerrado (abiertas y luego vendidas o alcanzado su stop), frente al mínimo que se considera una muestra fiable.',
        read: 'Por debajo del mínimo, cualquier estadística (hit rate, alpha...) puede ser puro ruido — hacen falta más operaciones cerradas antes de confiar en los números.',
    },
    dias_historico: {
        title: 'Días de histórico',
        what: 'Cuántos días de calendario llevan registrándose operaciones en este diario de papel, frente al mínimo considerado suficiente.',
        read: 'Un histórico corto puede no haber visto suficiente variedad de condiciones de mercado (subidas, caídas, lateral) para que el resultado sea representativo.',
    },
    resueltas_abiertas: {
        title: 'Resueltas / abiertas',
        what: 'Cuántas apuestas de papel ya se han resuelto (el mercado cerró y se sabe quién ganó) frente a las que siguen abiertas esperando resolución.',
        read: 'Los mercados de predicción tardan semanas o meses en resolverse — que haya muchas abiertas y pocas resueltas es normal al principio, no un fallo.',
    },
    rentabilidad_neta_apuesta: {
        title: 'Rentabilidad neta / apuesta',
        what: 'La ganancia o pérdida media, en %, por cada apuesta de papel cerrada, ya descontada una comisión estimada.',
        read: 'Positivo de forma sostenida (con suficientes apuestas resueltas) es la señal principal de que el modelo tiene una ventaja real, no solo suerte puntual.',
    },
    pnl_acumulado_papel: {
        title: 'P&L acumulado (papel)',
        what: 'La suma de ganancias y pérdidas de todas las apuestas de papel resueltas hasta ahora — dinero simulado, no real.',
        read: 'Es la cifra "de verdad ganarías esto" si hubieras apostado con dinero real desde el principio del experimento, en las mismas condiciones.',
    },
    ic95_roi: {
        title: 'IC95 rentabilidad neta',
        what: 'El límite inferior del intervalo de confianza al 95% de la rentabilidad neta media por apuesta — una forma estadística de decir "con alta confianza, la rentabilidad real es como mínimo esto".',
        read: 'Si este valor es positivo, hay evidencia estadística razonablemente sólida de ventaja real. Si es negativo (aunque la media observada sea positiva), los datos aún no descartan que todo sea puro azar.',
    },
    brier_score: {
        title: 'Puntuación de Brier',
        what: 'Mide lo bien calibradas que están unas probabilidades predichas frente a lo que realmente ocurrió.',
        read: 'Cuanto más bajo (cerca de 0), mejor calibrado. 0,25 es lo que darías prediciendo siempre "50%" a ciegas — por encima, el modelo predice peor que el azar puro.',
    },
    edge: {
        title: 'Edge (ventaja)',
        what: 'Los pocos factores que más sostienen la tesis de una idea, o la diferencia entre la probabilidad del modelo propio y la del mercado — el "por qué" en números.',
        read: 'Cuantos más factores coincidan y más fuerte su puntuación, más sólida la tesis. No garantiza acertar, solo dice que hay una discrepancia medible que explotar.',
    },
    hit_rate: {
        title: 'Hit rate (% de aciertos)',
        what: 'El porcentaje de operaciones o predicciones cerradas que resultaron ganadoras.',
        read: 'No basta por sí sola: un 40% puede ser rentable si las ganancias son mucho mayores que las pérdidas, y un 60% ruinoso si es al revés. Mírala siempre junto al P&L.',
    },
    horizonte: {
        title: 'Horizonte',
        what: 'La ventana de tiempo típica en la que se espera que una tesis se cumpla.',
        read: 'Momentum suele jugarse a 1-3 meses, valor/contrarian a 6-18 meses. No esperes resultados antes de ese plazo.',
    },
    tamano_sugerido: {
        title: 'Tamaño sugerido (position sizing)',
        what: 'Cuánto peso dar a una idea calculado al revés de su volatilidad: cuanto más se mueve, menos peso, para que cada posición aporte un riesgo parecido.',
        read: 'Es un punto de partida, no una regla fija — no tiene en cuenta la correlación con el resto de tu cartera, ajústalo con criterio.',
    },

    // ---------- Portfolio / dashboard ----------
    interes_compuesto: {
        title: 'Interés compuesto',
        what: 'El interés que generan tus ahorros se reinvierte y, a su vez, genera más interés — así tu dinero crece de forma acelerada, no lineal, cuanto más tiempo pasa.',
        read: 'El efecto es pequeño los primeros años y se dispara con el tiempo — por eso empezar antes importa más que aportar mucho más tarde. Esta calculadora asume una tasa anual constante, que en la práctica varía año a año.',
    },
    fire_number: {
        title: 'Número FIRE',
        what: 'El capital que necesitarías acumular para poder vivir de tus inversiones sin trabajar, calculado como tus gastos anuales dividido entre tu tasa de retiro segura.',
        read: 'Es una meta orientativa, no una garantía — asume que tus gastos y la rentabilidad futura se parecen a lo que has puesto en la calculadora, lo cual rara vez es exacto.',
    },
    swr: {
        title: 'Tasa de retiro segura (SWR)',
        what: 'El % de tu patrimonio que podrías retirar cada año, de por vida, con un riesgo razonablemente bajo de quedarte sin dinero — basado en estudios históricos de carteras diversificadas.',
        read: 'El 4% es la referencia clásica (regla del 4%), aunque muchos análisis recientes sugieren ser algo más conservador (3-3,5%) para horizontes muy largos. Cuanto más baja la tasa elegida, más capital necesitas, pero más seguro es el plan.',
    },
    dca_concept: {
        title: 'DCA (Dollar Cost Averaging)',
        what: 'Invertir una cantidad fija de forma periódica (p.ej. cada mes), en vez de meter todo el dinero de golpe — así compras más participaciones cuando el precio está bajo y menos cuando está alto, automáticamente.',
        read: 'No maximiza el retorno si el mercado sube sin parar, pero reduce el riesgo de invertir todo justo antes de una caída grande, y quita la presión de "acertar el momento".',
    },
    dividendos_proyectados: {
        title: 'Dividendos proyectados',
        what: 'Una estimación de los dividendos que cobrarías cada año si mantienes el capital invertido y el dividendo de la empresa/fondo crece a un ritmo constante.',
        read: 'Es una proyección, no una promesa — asume que el yield y su crecimiento se mantienen estables durante todos los años, algo que en la realidad varía con los resultados de las empresas.',
    },
    total_portfolio_value: {
        title: 'Valor Total de Cartera',
        what: 'La suma del valor de mercado de todas tus posiciones ahora mismo, convertido a euros.',
        read: 'Sube y baja cada día con el precio de mercado de tus activos — no significa que hayas metido o sacado dinero, solo que su valor cambió.',
    },
    best_performer: {
        title: 'Mejor rendimiento',
        what: 'La posición de tu cartera con mayor ganancia porcentual (P/L %) desde que la compraste.',
        read: 'Revisa también su peso en la cartera para saber cuánto ha aportado realmente al conjunto.',
    },
    worst_performer: {
        title: 'Peor rendimiento',
        what: 'La posición de tu cartera con mayor pérdida porcentual (P/L %) desde que la compraste.',
        read: 'Una pérdida grande en una posición pequeña pesa menos que una moderada en una posición grande — mira siempre junto al peso (%).',
    },
    dividends_ytd: {
        title: 'Dividendos YTD',
        what: 'El total de dividendos/cupones cobrados en efectivo desde el 1 de enero de este año.',
        read: 'Solo cuenta el dinero efectivamente recibido — si acabas de comprar una posición, tardará hasta el próximo pago en aparecer aquí.',
    },
    positions_count: {
        title: 'Posiciones',
        what: 'El número de activos distintos que tienes actualmente en cartera.',
        read: 'Más posiciones no siempre es mejor diversificación si están muy correlacionadas entre sí (p.ej. varias acciones del mismo sector).',
    },
    tu_posicion: {
        title: 'Tu posición',
        what: 'Cuántas unidades (acciones, participaciones o monedas) de este activo tienes actualmente.',
        read: 'Se actualiza automáticamente cada vez que compras, vendes o aportas a esta posición.',
    },
    valor_actual: {
        title: 'Valor actual',
        what: 'Lo que valen hoy, en euros, todas las unidades que tienes de este activo (cantidad × precio actual).',
        read: 'Cambia cada día con el precio de mercado, aunque no compres ni vendas nada.',
    },
    ganancia_perdida: {
        title: 'Ganancia/Pérdida',
        what: 'La diferencia entre el valor actual de la posición y lo que pagaste por ella.',
        read: 'Positivo (verde) = por encima de tu coste; negativo (rojo) = por debajo. No es una pérdida "real" hasta que vendas.',
    },
    peso_en_tu_cartera: {
        title: '% de tu cartera / Peso',
        what: 'Qué porcentaje del valor total de tu cartera representa esta posición.',
        read: 'Pesos muy altos en un solo activo (fuera de un núcleo indexado) significan que tu resultado global depende mucho de esa única apuesta.',
    },
    cantidad: {
        title: 'Cantidad',
        what: 'Cuántas unidades (acciones, participaciones o monedas) de este activo tienes en esta posición.',
        read: 'Junto al Precio Actual determina el Valor de la posición: Cantidad × Precio Actual.',
    },
    gain_loss: {
        title: 'P/L (ganancia o pérdida)',
        what: 'La diferencia en euros entre lo que vale hoy la posición y lo que costó comprarla.',
        read: 'Positivo (verde) = por encima de tu coste; negativo (rojo) = por debajo. Es "no realizado": solo se convierte en dinero real si vendes.',
    },
    gain_loss_pct: {
        title: 'P/L %',
        what: 'La misma ganancia/pérdida que el P/L en euros, pero en porcentaje sobre lo que invertiste.',
        read: 'Un +50€ en una posición pequeña puede ser un P/L% enorme, y en una grande, insignificante — por eso el % es más útil para comparar posiciones de tamaños distintos.',
    },
    coste_unidad: {
        title: 'Coste/Unidad',
        what: 'El precio medio al que compraste cada unidad de este activo, promediando todas tus compras si hiciste varias.',
        read: 'Compáralo con el Precio Actual: si es mayor, vas en positivo en esa posición; si es menor, vas en negativo.',
    },
    precio_actual: {
        title: 'Precio Actual',
        what: 'La última cotización de mercado conocida para este activo.',
        read: 'Es el precio "de hoy", no el que pagaste — la diferencia con tu coste es tu ganancia o pérdida no realizada.',
    },
    day_change: {
        title: 'Día % / Variación del día',
        what: 'Cuánto ha cambiado el precio o el valor desde el cierre anterior hasta ahora.',
        read: 'Es ruido de corto plazo — normal que oscile en ambas direcciones cada día. Solo preocupa si se repiten muchos días negativos y grandes seguidos.',
    },
    trend_spark: {
        title: 'Tendencia',
        what: 'Mini-gráfico con la evolución reciente (~30 días) del valor de TU posición en este activo, no del mercado en general.',
        read: 'Verde y subiendo = tu posición ha ganado valor recientemente; rojo y bajando = ha perdido. Solo se calcula para tus posiciones más grandes por peso.',
    },
};

function infoIcon(key) {
    if (!INFO_GLOSSARY[key]) return '';
    return `<button type="button" class="info-icon" data-info-key="${key}" aria-label="Qué es esto" onclick="event.stopPropagation(); openInfoIcon(this)">i</button>`;
}

(function () {
    let popover = null;

    function closePopover() {
        if (popover) { popover.remove(); popover = null; }
        document.removeEventListener('click', onOutsideClick, true);
        document.removeEventListener('keydown', onKeydown, true);
    }

    function onOutsideClick(e) {
        if (popover && !popover.contains(e.target)) closePopover();
    }

    function onKeydown(e) {
        if (e.key === 'Escape') closePopover();
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function openPopover(iconEl, entry) {
        closePopover();
        popover = document.createElement('div');
        popover.className = 'info-popover';
        popover.innerHTML = `
            <div class="info-popover-head">
                <strong>${escapeHtml(entry.title)}</strong>
                <button type="button" class="info-popover-close" aria-label="Cerrar">&times;</button>
            </div>
            <div class="info-popover-body">
                <p><span class="info-popover-label">Qué es</span>${escapeHtml(entry.what)}</p>
                <p><span class="info-popover-label">Cómo interpretarlo</span>${escapeHtml(entry.read)}</p>
            </div>
        `;
        document.body.appendChild(popover);

        const rect = iconEl.getBoundingClientRect();
        const pw = popover.offsetWidth, ph = popover.offsetHeight;
        let left = rect.left + rect.width / 2 - pw / 2;
        let top = rect.bottom + 8;
        const margin = 12;
        left = Math.max(margin, Math.min(left, window.innerWidth - pw - margin));
        if (top + ph > window.innerHeight - margin) top = rect.top - ph - 8;
        popover.style.left = `${left + window.scrollX}px`;
        popover.style.top = `${top + window.scrollY}px`;

        popover.querySelector('.info-popover-close').addEventListener('click', closePopover);
        setTimeout(() => {
            document.addEventListener('click', onOutsideClick, true);
            document.addEventListener('keydown', onKeydown, true);
        }, 0);
    }

    // Called directly from each icon's inline onclick (not via document-level
    // delegation): the icon's own onclick already calls stopPropagation() to
    // keep a click from also triggering a parent sortable <th> / clickable
    // row, which means a click on the icon never bubbles up to document —
    // relying on delegation here would silently never fire.
    window.openInfoIcon = function (iconEl) {
        const key = iconEl.dataset.infoKey;
        const entry = INFO_GLOSSARY[key];
        if (!entry) return;
        if (popover && popover.dataset.forKey === key) { closePopover(); return; }
        openPopover(iconEl, entry);
        popover.dataset.forKey = key;
    };
})();

window.infoIcon = infoIcon;
