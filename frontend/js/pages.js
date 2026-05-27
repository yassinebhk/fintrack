/**
 * Pages Management
 * Handles navigation between pages and dynamic content loading
 */

/**
 * Load learn page content from HTML file
 */
async function loadLearnPage(targetPage) {
    if (targetPage.dataset.loaded === 'true') return;
    
    try {
        const response = await fetch('pages/learn.html');
        if (response.ok) {
            targetPage.innerHTML = await response.text();
            targetPage.dataset.loaded = 'true';
        } else {
            targetPage.innerHTML = pageContent.learn;
        }
    } catch (error) {
        console.log('Loading fallback learn content');
        targetPage.innerHTML = pageContent.learn;
    }
}

// Page content templates (fallback)
const pageContent = {
    learn: `
<div class="learn-content">
    <h1>📚 Guía de Inversión</h1>

    <div style="background:linear-gradient(135deg,#6366f122,#00d4aa22); border:1px solid #6366f144; border-radius:10px; padding:14px 18px; margin:12px 0 18px;">
        <strong>🧭 Estás en el paso 1 de 3 del recorrido de FinTrack.</strong>
        <p style="margin:8px 0 0; font-size:14px;">Esta guía te enseña <strong>a invertir desde cero</strong>: conceptos, tipos de activos y las métricas que luego verás por toda la app. Cuando la domines, en <em>Documentación</em> verás <strong>cómo FinTrack automatiza todo esto por ti</strong>, y en <em>Polymarket Lab</em>, hacia dónde va el proyecto.</p>
        <p style="margin:8px 0 0; font-size:13px; color:#94a3b8;">Recorrido: <strong style="color:#00d4aa;">📚 Aprender (estás aquí)</strong> → 📖 Documentación → 🎲 Lab</p>
    </div>

    <div class="table-of-contents">
        <h4>Índice de Contenidos</h4>
        <ul>
            <li><a href="#conceptos-basicos">1. Conceptos Básicos de Inversión</a></li>
            <li><a href="#tipos-activos">2. Tipos de Activos</a></li>
            <li><a href="#metricas">3. Métricas y KPIs</a></li>
            <li><a href="#estrategias">4. Estrategias de Inversión</a></li>
            <li><a href="#riesgos">5. Gestión de Riesgos</a></li>
            <li><a href="#fiscalidad">6. Fiscalidad Básica</a></li>
        </ul>
    </div>

    <section id="conceptos-basicos">
        <h2>1. Conceptos Básicos de Inversión</h2>
        
        <h3>¿Qué es invertir?</h3>
        <p>Invertir significa poner tu dinero a trabajar con el objetivo de generar rendimientos a lo largo del tiempo. A diferencia del ahorro tradicional, donde tu dinero permanece estático, la inversión busca <strong>hacer crecer tu patrimonio</strong> aprovechando el poder del interés compuesto y el crecimiento económico.</p>
        
        <h3>El Interés Compuesto: La Octava Maravilla del Mundo</h3>
        <p>Albert Einstein supuestamente llamó al interés compuesto "la fuerza más poderosa del universo". El interés compuesto es el proceso por el cual los intereses generados se reinvierten y generan nuevos intereses.</p>
        
        <div class="formula-box">
            <p><strong>Fórmula del Interés Compuesto:</strong></p>
            <p class="formula">A = P × (1 + r/n)^(n×t)</p>
            <p class="text-muted" style="margin-top: 10px; font-size: 0.85rem;">
                Donde: A = Valor final | P = Capital inicial | r = Tasa de interés anual | n = Frecuencia de capitalización | t = Tiempo en años
            </p>
        </div>
        
        <div class="info-box success">
            <strong>💡 Ejemplo práctico:</strong> Si inviertes 10.000€ con un 7% de rentabilidad anual:
            <ul>
                <li>En 10 años: 19.672€</li>
                <li>En 20 años: 38.697€</li>
                <li>En 30 años: 76.123€</li>
            </ul>
            ¡Tu dinero se multiplica por 7.6 en 30 años!
        </div>
        
        <h3>Rentabilidad vs Riesgo</h3>
        <p>Existe una relación directa entre rentabilidad y riesgo: <strong>a mayor rentabilidad esperada, mayor riesgo</strong>. No existen inversiones con alta rentabilidad y bajo riesgo (y si alguien te las ofrece, probablemente sea una estafa).</p>
        
        <ul>
            <li><strong>Bajo riesgo:</strong> Depósitos bancarios, bonos del estado (1-3% anual)</li>
            <li><strong>Riesgo moderado:</strong> Bonos corporativos, fondos mixtos (3-6% anual)</li>
            <li><strong>Alto riesgo:</strong> Acciones, criptomonedas (7%+ anual, con alta volatilidad)</li>
        </ul>
    </section>

    <section id="tipos-activos">
        <h2>2. Tipos de Activos</h2>
        
        <h3>📈 Acciones (Stocks)</h3>
        <p>Las acciones representan una <strong>participación en la propiedad de una empresa</strong>. Al comprar acciones, te conviertes en accionista y tienes derecho a una parte proporcional de los beneficios (dividendos) y del valor de la empresa.</p>
        
        <p><strong>Ventajas:</strong></p>
        <ul>
            <li>Potencial de alta rentabilidad a largo plazo (históricamente 7-10% anual)</li>
            <li>Posibilidad de recibir dividendos</li>
            <li>Liquidez (puedes vender cuando quieras en horario de mercado)</li>
            <li>Participas en el crecimiento de empresas exitosas</li>
        </ul>
        
        <p><strong>Desventajas:</strong></p>
        <ul>
            <li>Alta volatilidad a corto plazo</li>
            <li>Requiere análisis y conocimiento</li>
            <li>Riesgo de pérdida total si la empresa quiebra</li>
        </ul>
        
        <h3>📊 ETFs (Exchange-Traded Funds)</h3>
        <p>Un ETF es un <strong>fondo de inversión que cotiza en bolsa</strong> como si fuera una acción. Permite invertir en un conjunto diversificado de activos con una sola compra.</p>
        
        <div class="info-box">
            <strong>Ejemplo:</strong> El ETF "VWCE" (Vanguard FTSE All-World) invierte en más de 3,000 empresas de todo el mundo. Con una sola compra, tienes exposición a la economía global.
        </div>
        
        <p><strong>Tipos de ETFs:</strong></p>
        <ul>
            <li><strong>ETFs de índices:</strong> Replican índices como S&P 500, MSCI World, etc.</li>
            <li><strong>ETFs sectoriales:</strong> Tecnología, salud, energía, etc.</li>
            <li><strong>ETFs de bonos:</strong> Renta fija diversificada</li>
            <li><strong>ETFs de materias primas:</strong> Oro, petróleo, etc.</li>
        </ul>
        
        <h3>🏦 Fondos Indexados</h3>
        <p>Los fondos indexados son fondos de inversión que <strong>replican un índice bursátil</strong> de forma pasiva. Son similares a los ETFs pero con algunas diferencias:</p>
        
        <table style="width: 100%; margin: 20px 0; border-collapse: collapse;">
            <thead>
                <tr style="border-bottom: 2px solid var(--border-secondary);">
                    <th style="text-align: left; padding: 10px;">Característica</th>
                    <th style="text-align: left; padding: 10px;">ETFs</th>
                    <th style="text-align: left; padding: 10px;">Fondos Indexados</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;">Negociación</td>
                    <td style="padding: 10px;">Tiempo real en bolsa</td>
                    <td style="padding: 10px;">Una vez al día (valor liquidativo)</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;">Comisiones</td>
                    <td style="padding: 10px;">Comisión de compra/venta</td>
                    <td style="padding: 10px;">Generalmente sin comisión</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;">Inversión mínima</td>
                    <td style="padding: 10px;">Precio de 1 participación</td>
                    <td style="padding: 10px;">Desde 1€ en algunos casos</td>
                </tr>
                <tr>
                    <td style="padding: 10px;">Fiscalidad (España)</td>
                    <td style="padding: 10px;">Tributas al vender</td>
                    <td style="padding: 10px;">Traspaso sin tributar</td>
                </tr>
            </tbody>
        </table>
        
        <h3>₿ Criptomonedas</h3>
        <p>Las criptomonedas son <strong>activos digitales descentralizados</strong> basados en tecnología blockchain. Son altamente especulativos y volátiles.</p>
        
        <div class="info-box warning">
            <strong>⚠️ Advertencia:</strong> Las criptomonedas son extremadamente volátiles. Solo invierte dinero que estés dispuesto a perder completamente. Caídas del 50-90% son comunes en este mercado.
        </div>
        
        <p><strong>Principales criptomonedas:</strong></p>
        <ul>
            <li><strong>Bitcoin (BTC):</strong> La primera y más conocida. "Oro digital"</li>
            <li><strong>Ethereum (ETH):</strong> Plataforma de contratos inteligentes</li>
            <li><strong>Stablecoins:</strong> Vinculadas al dólar (USDC, USDT)</li>
        </ul>
    </section>

    <section id="metricas">
        <h2>3. Métricas y KPIs</h2>
        
        <h3>📊 CAGR (Tasa de Crecimiento Anual Compuesto)</h3>
        <p>El CAGR es la tasa de rendimiento que se necesitaría para que una inversión crezca desde su valor inicial hasta su valor final, asumiendo que los beneficios se reinvierten al final de cada año.</p>
        
        <div class="formula-box">
            <p class="formula">CAGR = (Valor Final / Valor Inicial)^(1/años) - 1</p>
        </div>
        
        <p><strong>Interpretación:</strong></p>
        <ul>
            <li>CAGR del 7-10%: Excelente para renta variable a largo plazo</li>
            <li>CAGR del 3-5%: Típico de inversiones conservadoras</li>
            <li>CAGR negativo: La inversión ha perdido valor</li>
        </ul>
        
        <h3>📉 Maximum Drawdown (Máxima Caída)</h3>
        <p>El drawdown máximo mide la <strong>mayor caída desde un máximo hasta un mínimo</strong> antes de alcanzar un nuevo máximo. Es crucial para entender el riesgo de una inversión.</p>
        
        <div class="formula-box">
            <p class="formula">Drawdown = (Valor Máximo - Valor Mínimo) / Valor Máximo × 100%</p>
        </div>
        
        <p><strong>Ejemplos históricos:</strong></p>
        <ul>
            <li>Crisis 2008: S&P 500 cayó un 56%</li>
            <li>COVID 2020: S&P 500 cayó un 34%</li>
            <li>Bitcoin 2022: Cayó un 77%</li>
        </ul>
        
        <h3>📈 Ratio de Sharpe</h3>
        <p>El ratio de Sharpe mide la <strong>rentabilidad ajustada al riesgo</strong>. Indica cuánto exceso de rentabilidad obtienes por cada unidad de riesgo asumido.</p>
        
        <div class="formula-box">
            <p class="formula">Sharpe = (Rentabilidad Cartera - Tasa Libre de Riesgo) / Volatilidad</p>
        </div>
        
        <p><strong>Interpretación:</strong></p>
        <ul>
            <li><strong>< 1:</strong> Rentabilidad insuficiente para el riesgo asumido</li>
            <li><strong>1 - 2:</strong> Buena relación rentabilidad/riesgo</li>
            <li><strong>> 2:</strong> Excelente (difícil de mantener a largo plazo)</li>
        </ul>
        
        <h3>📊 Volatilidad</h3>
        <p>La volatilidad mide las <strong>fluctuaciones en el precio</strong> de un activo. Se expresa como la desviación estándar de los rendimientos, generalmente anualizada.</p>
        
        <ul>
            <li><strong>Baja volatilidad (< 10%):</strong> Bonos, activos defensivos</li>
            <li><strong>Media volatilidad (10-20%):</strong> Acciones de gran capitalización</li>
            <li><strong>Alta volatilidad (> 20%):</strong> Acciones growth, criptomonedas</li>
        </ul>
    </section>

    <section id="estrategias">
        <h2>4. Estrategias de Inversión</h2>
        
        <h3>🔄 DCA (Dollar Cost Averaging)</h3>
        <p>El DCA consiste en <strong>invertir cantidades fijas de dinero a intervalos regulares</strong>, independientemente del precio del activo. Esta estrategia:</p>
        
        <ul>
            <li>Reduce el impacto de la volatilidad</li>
            <li>Elimina la necesidad de "timing" del mercado</li>
            <li>Convierte la inversión en un hábito</li>
            <li>Reduce el estrés emocional</li>
        </ul>
        
        <div class="info-box success">
            <strong>💡 Ejemplo:</strong> Inviertes 500€ cada mes en un ETF global:
            <ul>
                <li>Mes 1: Precio 100€ → Compras 5 participaciones</li>
                <li>Mes 2: Precio 80€ → Compras 6.25 participaciones</li>
                <li>Mes 3: Precio 120€ → Compras 4.17 participaciones</li>
            </ul>
            Tu precio medio: 96.77€ (mejor que el promedio de 100€)
        </div>
        
        <h3>🌍 Diversificación</h3>
        <p>La diversificación consiste en <strong>distribuir las inversiones entre diferentes activos</strong> para reducir el riesgo. "No pongas todos los huevos en la misma cesta".</p>
        
        <p><strong>Niveles de diversificación:</strong></p>
        <ul>
            <li><strong>Por clase de activo:</strong> Acciones, bonos, inmobiliario, etc.</li>
            <li><strong>Por geografía:</strong> USA, Europa, mercados emergentes</li>
            <li><strong>Por sector:</strong> Tecnología, salud, finanzas, etc.</li>
            <li><strong>Por tamaño:</strong> Large cap, mid cap, small cap</li>
        </ul>
        
        <h3>📊 Asset Allocation</h3>
        <p>El asset allocation es la <strong>distribución estratégica de tu cartera</strong> entre diferentes clases de activos. Ejemplos típicos:</p>
        
        <ul>
            <li><strong>Cartera agresiva (joven):</strong> 90% acciones, 10% bonos</li>
            <li><strong>Cartera moderada:</strong> 60% acciones, 40% bonos</li>
            <li><strong>Cartera conservadora:</strong> 30% acciones, 70% bonos</li>
        </ul>
        
        <h3>🔥 Estrategia FIRE</h3>
        <p>FIRE (Financial Independence, Retire Early) es un movimiento que busca la <strong>independencia financiera</strong> mediante el ahorro agresivo y la inversión inteligente.</p>
        
        <p><strong>La regla del 4%:</strong> Puedes retirar el 4% de tu cartera anualmente con alta probabilidad de no quedarte sin dinero en 30+ años.</p>
        
        <div class="formula-box">
            <p class="formula">Número FIRE = Gastos Anuales × 25</p>
            <p class="text-muted" style="margin-top: 10px;">Si gastas 24.000€/año, necesitas 600.000€ para ser FIRE</p>
        </div>
    </section>

    <section id="riesgos">
        <h2>5. Gestión de Riesgos</h2>
        
        <h3>Tipos de Riesgo</h3>
        <ul>
            <li><strong>Riesgo de mercado:</strong> Caídas generales del mercado</li>
            <li><strong>Riesgo específico:</strong> Problemas en una empresa concreta</li>
            <li><strong>Riesgo de divisa:</strong> Fluctuaciones en tipos de cambio</li>
            <li><strong>Riesgo de liquidez:</strong> Dificultad para vender un activo</li>
            <li><strong>Riesgo de inflación:</strong> Pérdida de poder adquisitivo</li>
        </ul>
        
        <h3>Cómo Gestionar el Riesgo</h3>
        <ol>
            <li><strong>Diversifica:</strong> No concentres más del 5-10% en un solo activo</li>
            <li><strong>Invierte a largo plazo:</strong> El tiempo reduce la volatilidad</li>
            <li><strong>Mantén un fondo de emergencia:</strong> 3-6 meses de gastos en efectivo</li>
            <li><strong>Rebalancea periódicamente:</strong> Mantén tu asset allocation objetivo</li>
            <li><strong>No inviertas dinero que necesites a corto plazo</strong></li>
        </ol>
    </section>

    <section id="fiscalidad">
        <h2>6. Fiscalidad Básica (España)</h2>
        
        <div class="info-box warning">
            <strong>⚠️ Disclaimer:</strong> Esta información es orientativa. Consulta siempre con un asesor fiscal para tu situación particular.
        </div>
        
        <h3>Tributación de Ganancias Patrimoniales</h3>
        <p>Las ganancias de inversiones tributan en la base del ahorro:</p>
        <ul>
            <li>Hasta 6.000€: 19%</li>
            <li>6.000€ - 50.000€: 21%</li>
            <li>50.000€ - 200.000€: 23%</li>
            <li>200.000€ - 300.000€: 27%</li>
            <li>Más de 300.000€: 28%</li>
        </ul>
        
        <h3>Compensación de Pérdidas</h3>
        <p>Puedes compensar ganancias con pérdidas del mismo año. Las pérdidas no compensadas se pueden arrastrar 4 años.</p>
        
        <h3>Ventaja de los Fondos de Inversión</h3>
        <p>Los traspasos entre fondos de inversión (no ETFs) no tributan hasta que retiras el dinero. Esto permite el <strong>diferimiento fiscal</strong>.</p>
    </section>

    <div style="background:#00d4aa14; border:1px solid #00d4aa44; border-radius:10px; padding:16px 18px; margin-top:24px; text-align:center;">
        <strong style="font-size:15px;">✅ Ya entiendes los fundamentos. Siguiente paso →</strong>
        <p style="margin:8px 0 12px; font-size:14px;">Ahora descubre <strong>cómo FinTrack aplica todo esto automáticamente</strong> cada día: cómo lee tu cartera, escanea el mercado y te trae oportunidades explicadas.</p>
        <a href="#" onclick="document.querySelector('[data-page=docs]').click(); return false;" style="display:inline-block; background:#00d4aa; color:#04121a; font-weight:600; padding:8px 18px; border-radius:8px; text-decoration:none;">📖 Ir a Documentación →</a>
    </div>
</div>
    `,

    docs: `
<div class="docs-content">
    <h1>📖 Documentación de FinTrack</h1>

    <div style="background:linear-gradient(135deg,#6366f122,#00d4aa22); border:1px solid #6366f144; border-radius:10px; padding:14px 18px; margin:12px 0 18px;">
        <strong>🧭 Paso 2 de 3 del recorrido.</strong>
        <p style="margin:8px 0 0; font-size:14px;">Aquí ves <strong>qué es FinTrack, cómo se usa cada pestaña y cómo "piensa"</strong> para descubrir oportunidades. Si te falta base sobre métricas como Sharpe o momentum, repásalas primero en <em>Aprender</em>.</p>
        <p style="margin:8px 0 0; font-size:13px; color:#94a3b8;">Recorrido: 📚 Aprender → <strong style="color:#00d4aa;">📖 Documentación (estás aquí)</strong> → 🎲 Lab</p>
    </div>

    <div class="table-of-contents">
        <h4>Índice</h4>
        <p style="font-size:13px; color:#94a3b8; margin:0 0 8px;">Léelo de arriba abajo: va de <em>qué es</em> → <em>cómo se usa</em> → <em>cómo funciona por dentro</em> → <em>detalle técnico</em>.</p>
        <ul>
            <li><strong>Empezar aquí</strong></li>
            <li style="margin-left:14px;"><a href="#que-es">🎯 Qué es FinTrack y la visión</a></li>
            <li style="margin-left:14px;"><a href="#guia-uso">🧭 Guía de uso: pestaña por pestaña</a></li>
            <li style="margin-left:14px;"><a href="#el-cerebro">🧠 El cerebro: cómo descubre y recomienda (paso a paso)</a></li>
            <li style="margin-top:6px;"><strong>Cómo razona (los algoritmos)</strong></li>
            <li style="margin-left:14px;"><a href="#novedades">🆕 Novedades (asistente autónomo con IA)</a></li>
            <li style="margin-left:14px;"><a href="#algoritmos">🔬 Cómo funcionan nuestros algoritmos (teoría + ejemplos)</a></li>
            <li style="margin-top:6px;"><strong>Referencia técnica (cómo está montado)</strong></li>
            <li style="margin-left:14px;"><a href="#arquitectura">🏗️ Arquitectura del Sistema</a></li>
            <li style="margin-left:14px;"><a href="#inicio-rapido">Inicio Rápido</a></li>
            <li style="margin-left:14px;"><a href="#configuracion">Configuración</a></li>
            <li style="margin-left:14px;"><a href="#añadir-posiciones">Añadir Posiciones</a></li>
            <li style="margin-left:14px;"><a href="#funcionalidades">Funcionalidades</a></li>
            <li style="margin-left:14px;"><a href="#api">API Reference</a></li>
            <li style="margin-left:14px;"><a href="#faq">Preguntas Frecuentes</a></li>
        </ul>
    </div>

    <!-- ==================== QUÉ ES FINTRACK ==================== -->
    <section id="que-es">
        <h2>🎯 Qué es FinTrack y la visión</h2>
        <p>FinTrack es tu <strong>asistente de inversión personal</strong>. No es solo un panel para mirar cuánto vale tu cartera: cada día <strong>rastrea el mercado, lo analiza con un motor cuantitativo y te trae oportunidades concretas y explicadas</strong>, tanto en la web como por Telegram.</p>
        <p>La idea de fondo: que las decisiones se apoyen en <strong>datos y estadística</strong> (no en la intuición de una IA), y que la IA se limite a <strong>explicarte</strong> en lenguaje claro lo que los números ya han decidido.</p>
        <div class="formula-box">
            <p><strong>En una frase:</strong></p>
            <p style="font-size:15px;">Tú llevas tus inversiones reales (Kraken, Trade Republic, MyInvestor) → FinTrack las une, las valora con precios reales, y cada mañana te propone <em>qué mirar hoy</em> con su porqué.</p>
        </div>
        <h3>¿Qué hace por ti?</h3>
        <ul>
            <li><strong>Une toda tu cartera</strong> en un sitio, con precios actualizados (como abrir cada app por separado, pero de golpe).</li>
            <li><strong>Descubre oportunidades nuevas</strong> que quizá no conoces, filtrando lo que ya tienes.</li>
            <li><strong>Te explica el porqué</strong> de cada idea: tendencia, riesgo, noticias que la respaldan y una gráfica.</li>
            <li><strong>Te avisa</strong> (alertas y resumen diario) y responde tus preguntas por Telegram.</li>
        </ul>
        <p style="background:#f59e0b18; border-left:3px solid #f59e0b; padding:10px 14px; border-radius:6px;"><strong>Importante y honesto:</strong> FinTrack <em>no predice el futuro</em> ni da órdenes de compra. Es análisis educativo para ayudarte a decidir mejor. Tú mandas.</p>
    </section>

    <!-- ==================== GUÍA DE USO ==================== -->
    <section id="guia-uso">
        <h2>🧭 Guía de uso: pestaña por pestaña</h2>
        <p>Un recorrido por la app en el orden en que la usarías:</p>

        <h3>1. 📊 Dashboard</h3>
        <p>Tu foto global: valor total, ganancia/pérdida, evolución histórica y reparto por tipo de activo. Es lo primero que ves al entrar.</p>

        <h3>2. 💼 Gestionar Cartera</h3>
        <p>Aquí registras lo que tienes y los <strong>movimientos reales</strong> que haces en tus apps de trading. Cuando aportas dinero a un activo puedes indicar <strong>desde qué broker y en qué fecha</strong>, y FinTrack calcula las participaciones al precio de ese instante para mantener un registro fiel.</p>

        <h3>3. 💡 Oportunidades</h3>
        <p>El corazón del asistente. Cada día muestra:</p>
        <ul>
            <li><strong>Régimen de mercado</strong> (alcista/bajista/neutral) según la amplitud del mercado.</li>
            <li><strong>Tendencias del momento</strong>: qué ETFs/fondos y cripto más han crecido y qué patrones comparten.</li>
            <li><strong>2-4 oportunidades</strong> con gráfica a 6 meses, noticias que las respaldan y el desglose de por qué el motor las puntúa así.</li>
            <li><strong>Ranking cuantitativo</strong> de sectores (puntuación objetiva, no opinión).</li>
        </ul>

        <h3>4. 🔔 Alertas</h3>
        <p>Reglas que vigilan tu cartera y el mercado (caídas, noticias relevantes agrupadas por activo) y te avisan por Telegram.</p>

        <h3>5. 🧮 Calculadoras y 📈 Backtest</h3>
        <p>Herramientas para simular interés compuesto, aportaciones periódicas y para <em>probar</em> cómo se habría comportado una estrategia en el pasado.</p>

        <h3>6. 🤖 Asesor IA y 📰 Noticias</h3>
        <p>Chat con contexto de tu cartera para resolver dudas, y un agregador de noticias financieras con su sentimiento (positivo/negativo) clasificado por IA.</p>

        <h3>7. 📱 Telegram</h3>
        <p>Todo lo anterior, en tu bolsillo: <code>/cartera</code>, <code>/oportunidades</code>, <code>/aportar</code>, resumen diario, gráficas como imagen y preguntas en lenguaje natural. El bot muestra que "está pensando" hasta que responde.</p>
    </section>

    <!-- ==================== EL CEREBRO ==================== -->
    <section id="el-cerebro">
        <h2>🧠 El cerebro: cómo descubre y recomienda (paso a paso)</h2>
        <p>Cuando pides oportunidades (o a las 07:30 automáticamente), esto es lo que ocurre <strong>de principio a fin</strong>:</p>
        <pre class="diagram-box">
1. 📥 LEE TU CARTERA      → para no recomendarte lo que ya tienes y diversificar tu riesgo.

2. 🌐 ESCANEA EL MERCADO   → ~100 ETFs/fondos curados + screeners de Yahoo (infravaloradas,
                             growth de calidad) + una cesta de cripto. Datos reales de precio.

3. 🔬 PUNTÚA CON EL MOTOR  → cada activo pasa por un ENSEMBLE de criterios (jueces):
   (estadística, no IA)      momentum · régimen/tendencia · Sharpe · técnico (RSI/MACD)
                             · volatilidad EWMA · reversión a la media.
                             Cada juez "vota" con un z-score; convergen en 2 puntuaciones:
                             MOMENTUM (lo fuerte) y VALOR (lo castigado pero de calidad).

4. 📡 DETECTA EL RÉGIMEN    → % de activos sobre su tendencia de 200 sesiones.
                             Alcista → pesa más momentum. Bajista → pesa más valor/defensivo.

5. 🚀 ANALIZA TENDENCIAS    → qué ha crecido más y qué patrones comparten los líderes.

6. 📰 AÑADE NOTICIAS+MACRO   → titulares recientes (con sentimiento) y contexto macro.

7. 🤖 LA IA EXPLICA          → Gemini coge SOLO lo mejor rankeado y lo redacta: qué es,
   (no decide, narra)        por qué ahora, riesgos, encaje en tu cartera. Usa el ticker real.

8. 📈 AÑADE EVIDENCIA        → gráfica de 6 meses + noticias que respaldan cada idea.

9. 📤 TE LO ENTREGA          → web (tarjetas + desglose) y Telegram (gráfica + criterios).
        </pre>
        <p>La clave: <strong>los pasos 2-6 son pura estadística</strong> sobre datos reales; la IA (paso 7) solo <strong>explica</strong> lo que el motor ya ordenó. Por eso puedes ver el "porqué" de cada idea con el desglose de criterios. El detalle matemático de cada juez está en <a href="#algoritmos">🔬 Cómo funcionan nuestros algoritmos</a>.</p>
    </section>

    <!-- ==================== NOVEDADES ==================== -->
    <section id="novedades">
        <h2>🆕 Novedades — el salto a asistente autónomo con IA</h2>
        <p>FinTrack pasó de ser un panel de cartera a un <strong>asistente de inversión que cada día rastrea el mercado, lo analiza con un motor cuantitativo y te trae oportunidades explicadas</strong>. Estas son las funcionalidades añadidas recientemente:</p>

        <h3>🔎 Descubrimiento de oportunidades (datos, no opinión de la IA)</h3>
        <ul>
            <li><strong>Universo amplio</strong>: ~100 ETFs/fondos reales (sectores, regiones, factores, temáticos, materias primas, renta fija) + <strong>screeners dinámicos de Yahoo</strong> (infravaloradas, growth de calidad) que cada día aportan nombres nuevos. Excluye lo que ya tienes en cartera, así las ideas son <em>de verdad</em> nuevas.</li>
            <li><strong>Motor cuantitativo</strong> (librerías validadas <code>empyrical</code> + <code>ta</code>): puntúa cada activo de forma objetiva. La IA <strong>no decide</strong> qué recomendar; solo <strong>explica</strong> lo que el motor ranquea arriba, usando el ticker real verificado.</li>
            <li><strong>Mix momentum + valor</strong>: dos rankings paralelos para no recomendar solo cosas en máximos.</li>
        </ul>

        <h3>🧩 Ensemble multi-criterio + régimen de mercado</h3>
        <ul>
            <li>Varios <strong>criterios independientes "votan"</strong> (momentum multi-periodo, momentum absoluto/tendencia, Sharpe/Sortino, técnico RSI/MACD, volatilidad EWMA, reversión a la media) y convergen en una convicción.</li>
            <li><strong>Desglose transparente</strong>: en la web ves una barra por criterio ("🧮 Por qué lo puntúa así"); en Telegram, los 3 criterios principales. Nada de caja negra.</li>
            <li><strong>Régimen de mercado por amplitud</strong> (% de activos sobre su media de 200 sesiones): en mercado alcista pesa más el momentum, en bajista el valor/defensivo.</li>
        </ul>

        <h3>🚀 Tendencias del momento (ganadores + patrones)</h3>
        <ul>
            <li>Detecta <strong>qué ETFs/fondos y cripto más han crecido</strong> en los últimos meses y extrae <strong>patrones comunes</strong> (¿están sobre su tendencia? ¿qué temas/regiones dominan? ¿están sobrecomprados?).</li>
            <li>Mide la <strong>afinidad de cada candidato con el "perfil ganador" actual</strong>, como contexto adicional — con aviso honesto del riesgo de comprar caro.</li>
        </ul>

        <h3>📈 Cada oportunidad, con evidencia</h3>
        <ul>
            <li><strong>Gráfica de tendencia a 6 meses</strong> (verde/rojo según dirección) generada en el momento.</li>
            <li><strong>Noticias que la respaldan</strong>, con fuente y enlace (la IA referencia titulares reales por índice, no inventa).</li>
        </ul>

        <h3>🤖 Telegram bidireccional</h3>
        <ul>
            <li><code>/oportunidades</code>, <code>/cartera</code>, <code>/aportar</code>; resumen diario con precios reales; nombres amigables (no ISINs); gráficas como imagen.</li>
            <li><strong>Registro de movimientos reales</strong>: "mete 50€ al oro desde Kraken el día X" → calcula participaciones al precio de ese instante y mantiene el ledger real.</li>
            <li><strong>Indicador "pensando"</strong> que se mantiene visible (typing) hasta que responde.</li>
        </ul>

        <h3>⚙️ Robustez e infraestructura</h3>
        <ul>
            <li><strong>Persistencia en PostgreSQL</strong> (sobrevive a los redeploys de Render).</li>
            <li><strong>LLM Gemini con fallback a Groq</strong> ante límites de cuota; sentimiento de noticias clasificado por LLM.</li>
            <li><strong>Pre-calentamiento diario a las 07:30</strong>: las oportunidades se generan por adelantado para que tu primera visita sea instantánea. Caché de 20h y bloqueo anti-escaneos concurrentes.</li>
            <li>Indicador de "pensando" también en la web (spinner + mensajes rotativos) para el cálculo en frío.</li>
        </ul>
    </section>

    <!-- ==================== ALGORITMOS ==================== -->
    <section id="algoritmos">
        <h2>🔬 Cómo funcionan nuestros algoritmos (teoría + ejemplos)</h2>
        <p>Esta sección explica <strong>la estadística que usamos para ranquear inversiones</strong> — el "porqué" de cada puntuación. Es independiente de <em>cómo está montada la app</em> (eso está más abajo, en <a href="#arquitectura">Referencia técnica</a>). Aquí hablamos de <strong>métodos</strong>, no de servidores.</p>
        <p style="background:#f59e0b18; border-left:3px solid #f59e0b; padding:10px 14px; border-radius:6px;">
            <strong>Honestidad ante todo:</strong> estos métodos <em>no predicen el precio futuro</em>. Miden tendencia, riesgo y posición relativa sobre datos ya ocurridos, y rankean. Cualquiera que prometa "predecir" el precio con un indicador, miente. Nuestro objetivo es <strong>ranquear con criterio estadístico</strong>, no adivinar.
        </p>
        <p>La idea global: cada activo pasa por <strong>varios "jueces" independientes</strong> (momentum, riesgo, técnico, régimen, volatilidad, reversión). Cada juez emite un voto numérico; los votos se combinan en dos puntuaciones — <strong>MOMENTUM</strong> (lo fuerte que sube con calidad) y <strong>VALOR</strong> (lo castigado pero sano) — y puedes ver el voto de cada juez en el desglose de cada idea. Vamos juez por juez.</p>

        <h3>① Momentum multi-periodo (estilo HQM)</h3>
        <p><strong>Qué mide:</strong> la fuerza de la tendencia combinando varios horizontes.<br>
        <strong>Intuición:</strong> es la anomalía más documentada de las finanzas (Jegadeesh &amp; Titman, 1993): lo que ha subido de forma sostenida tiende a seguir subiendo a medio plazo. Usamos varios plazos (1, 3, 6 y 12 meses) para premiar la tendencia <em>sostenida</em> y no un pico de un solo mes.</p>
        <pre class="diagram-box">momentum = media( ret_1m , ret_3m , ret_6m , ret_12m )

Ejemplo A (sostenido):  +5% (1m), +18% (3m), +30% (6m), +45% (1a)
        → (5+18+30+45)/4 = +24,5%   tendencia fuerte y consistente ✔
Ejemplo B (espejismo):  +20% (1m), +2% (3m), −5% (6m), −10% (1a)
        → (20+2−5−10)/4 = +1,75%    subida reciente sin base ✘</pre>
        <p><strong>Qué decide:</strong> es el principal motor de la tesis MOMENTUM.</p>

        <h3>② Métricas de riesgo ajustado (librería empyrical, de Quantopian)</h3>
        <p><strong>Qué miden:</strong> no basta con cuánto sube algo, sino <em>cuánto riesgo</em> asumes para ese retorno.</p>
        <ul>
            <li><strong>Ratio de Sharpe</strong> = retorno / volatilidad total. Premio por unidad de riesgo. &gt;1 bueno, &gt;2 muy bueno.</li>
            <li><strong>Sortino</strong>: como Sharpe pero solo penaliza la volatilidad <em>a la baja</em> (que algo suba a saltos no es "malo").</li>
            <li><strong>Máximo drawdown</strong>: la peor caída desde un máximo. Mide el "dolor" máximo que habrías sufrido.</li>
            <li><strong>Volatilidad anualizada</strong>: cuánto oscila, en términos anuales.</li>
        </ul>
        <pre class="diagram-box">Activo A: +20% anual, volatilidad 10%  → Sharpe ≈ 2,0   excelente
Activo B: +20% anual, volatilidad 40%  → Sharpe ≈ 0,5   mismo retorno, mucho peor
El motor prefiere A: mismo premio con muchos menos sustos.</pre>
        <p><strong>Qué decide:</strong> el Sharpe entra como "juez de calidad" tanto en MOMENTUM como en VALOR — evita recomendar algo que sube dando bandazos o que cae sin calidad.</p>

        <h3>③ Indicadores técnicos (librería ta — RSI, MACD, medias, Bollinger)</h3>
        <p><strong>Qué miden:</strong> el "pulso" de corto plazo y el <em>timing</em>.</p>
        <ul>
            <li><strong>RSI(14)</strong>: termómetro de 0 a 100. &lt;30 = sobreventa (posible entrada); &gt;70 = sobrecompra (cuidado, puede estar caro).</li>
            <li><strong>MACD</strong>: detecta cambios de tendencia mediante el cruce de dos medias móviles (señal alcista/bajista).</li>
            <li><strong>SMA50 vs SMA200</strong>: cuando la media de 50 días supera a la de 200 es una "golden cross" (alcista); al revés, "death cross".</li>
            <li><strong>Bollinger %B</strong>: dónde está el precio dentro de su banda de volatilidad (cerca del techo o del suelo).</li>
        </ul>
        <pre class="diagram-box">Ejemplo: RSI 72 + MACD alcista + precio sobre SMA200
       → tendencia confirmada pero sobrecomprado: bueno por momentum,
         pero el motor avisa de que el timing de entrada es arriesgado.</pre>
        <p><strong>Qué decide:</strong> confirma la dirección (suma al MOMENTUM) y marca sobreventa (suma al VALOR).</p>

        <h3>④ Momentum absoluto / régimen de tendencia</h3>
        <p><strong>Qué mide:</strong> si el activo está <em>por encima de su propia tendencia de largo plazo</em> (media de 200 sesiones). Es la idea del "Dual Momentum" de Gary Antonacci.<br>
        <strong>Intuición:</strong> no basta con que suba más que otros (momentum relativo); también debe estar en tendencia alcista <em>en términos absolutos</em>. Así evitamos recomendar algo que "cae menos que el resto" pero sigue rompiendo a la baja.</p>
        <pre class="diagram-box">dist_200 = (precio − media_200d) / media_200d
+0,15  → un 15% por encima de su tendencia (sano, alcista)
−0,20  → un 20% por debajo (estructuralmente bajista, ojo)</pre>

        <h3>⑤ Volatilidad EWMA (RiskMetrics, λ = 0,94)</h3>
        <p><strong>Qué mide:</strong> el riesgo reciente, dando <strong>más peso a los últimos días</strong>. Reacciona antes que la volatilidad simple cuando el mercado se pone nervioso. Es el estándar de la industria (RiskMetrics de J.P. Morgan) para dimensionar riesgo.</p>
        <pre class="diagram-box">var_hoy = 0,94 · var_ayer + 0,06 · retorno_hoy²   (media exponencial)
Resultado: si la volatilidad se dispara esta semana, el motor lo "ve"
           enseguida y penaliza ese activo, aunque su media anual sea baja.</pre>
        <p><strong>Qué decide:</strong> penaliza la alta volatilidad en ambas tesis (preferimos llegar al mismo sitio con menos sobresaltos).</p>

        <h3>⑥ Reversión a la media</h3>
        <p><strong>Qué mide:</strong> cuántas desviaciones típicas se aleja el precio de su media de 50 sesiones.<br>
        <strong>Intuición:</strong> los precios tienden a "volver" hacia su media. Muy por debajo puede ser una oportunidad de rebote (tesis valor/contrarian); muy por encima, que está estirado.</p>
        <pre class="diagram-box">z = (precio − media_50d) / desviación_típica_50d
z = −2,0  → 2σ por debajo de su media: sobrevendido, candidato a rebote
z = +2,5  → muy estirado por encima: cuidado si entras ahora</pre>
        <p><strong>Qué decide:</strong> es un motor clave de la tesis VALOR/CONTRARIAN.</p>

        <h3>⑦ Normalización transversal: z-score winsorizado</h3>
        <p><strong>El problema:</strong> ¿cómo comparas "momentum +24%" con "Sharpe 2,1" o "RSI 35"? Son unidades distintas. <strong>La solución:</strong> convertimos cada métrica a "¿cuántas desviaciones típicas se aparta de la media de TODO el universo de hoy?". Así todo queda en la misma escala comparable, y recortamos los extremos a ±3σ (<em>winsorización</em>) para que un dato loco no distorsione el ranking.</p>
        <pre class="diagram-box">z = (valor − media_del_universo) / desviación_del_universo , recortado a [−3, +3]

"momentum +24%" cuando la media del universo es +8% y σ=9%
   → z = (24 − 8) / 9 ≈ +1,8σ   → "está claramente por encima de la media de hoy"</pre>
        <p><strong>Por qué importa:</strong> hace que los criterios sean <em>comparables y combinables</em>. Cada "voto" de un juez es, en realidad, su z-score.</p>

        <h3>⑧ El ensemble: cómo convergen los criterios en una decisión</h3>
        <p>Aquí está la idea que pediste: <strong>varios criterios convergiendo</strong>. Cada juez vota con su z-score; combinamos los votos con pesos en dos tesis. Lo importante: <strong>puedes ver el voto de cada juez</strong> (en la web, "🧮 Por qué lo puntúa así").</p>
        <pre class="diagram-box">TESIS MOMENTUM = suma ponderada de jueces:
  momentum (tendencia)   0,28 · z
  régimen (sobre 200d)   0,22 · z
  riesgo (Sharpe)        0,20 · z
  técnico (RSI/MACD)     0,15 · z
  volatilidad (EWMA)     0,15 · (−z)   ← penaliza ser volátil

Ejemplo real (SOXX, semis):
  momentum +0,84 · régimen +0,66 · Sharpe +0,52 · técnico +0,24 · volatilidad −0,43
  ──────────────────────────────────────────────────────────────────
  → puntuación agregada +2,01  → CONVICCIÓN ALTA</pre>
        <p>La tesis <strong>VALOR/CONTRARIAN</strong> usa otros jueces con otros pesos: infravaloración (posición baja en su rango anual), reversión a la media, sobreventa (RSI bajo) y <em>calidad</em> (Sharpe). Ese juez de calidad evita que <strong>un activo barato pero malo</strong> (que cae por buenas razones) engañe al sistema.</p>
        <p>Y por encima de todo, el <strong>régimen de mercado modula los pesos</strong>: en mercado alcista pesa más el momentum; en bajista, el valor/defensivo (siguiente punto).</p>

        <h3>⑨ Régimen de mercado por amplitud (breadth)</h3>
        <p><strong>Qué mide:</strong> el "clima" general del mercado, con un indicador clásico de amplitud: <strong>qué % de activos están sobre su media de 200 sesiones</strong>.</p>
        <pre class="diagram-box">&gt; 55% de activos en tendencia alcista  → RÉGIMEN ALCISTA  (×1,10 momentum, ×0,95 valor)
&lt; 45%                                  → RÉGIMEN BAJISTA  (×0,85 momentum, ×1,10 valor)
en medio                                → NEUTRAL</pre>
        <p><strong>Qué decide:</strong> adapta el sistema al contexto — no tiene sentido perseguir momentum en un mercado que se está girando a la baja.</p>

        <h3>⑩ Tendencias y "perfil ganador"</h3>
        <p>Después de puntuar, miramos qué más ha crecido (ETFs, fondos y cripto) y qué <strong>rasgos comparten los líderes</strong>: ¿están sobre su tendencia?, ¿qué temas/regiones dominan?, ¿están sobrecomprados? Medimos cuánto se parece cada candidato a ese "perfil ganador". Es <strong>contexto</strong>, no una orden: si el patrón está muy extendido (RSI alto), se avisa del riesgo de comprar caro.</p>

        <h3>🔗 De la estadística a la explicación</h3>
        <p>Todo lo anterior produce un <strong>ranking objetivo</strong>. Solo entonces entra la IA (Gemini), y <strong>únicamente para explicar</strong> en lenguaje claro las ideas mejor puntuadas (qué es, por qué ahora, riesgos, encaje). La IA <em>no</em> decide el orden ni inventa tickers. El recorrido completo está en <a href="#el-cerebro">El cerebro: cómo descubre y recomienda</a>.</p>

        <h3>📚 Lo que NO usamos (a propósito)</h3>
        <p>Deep Learning (LSTM/Transformers) para "predecir precio": muy popular en YouTube, pero la investigación seria (Gu, Kelly &amp; Xiu, 2020) muestra que rara vez bate a métodos simples fuera de muestra y se sobreajusta con facilidad. El consenso (López de Prado) avisa: <strong>el enemigo no es el algoritmo, es el sobreajuste</strong>. Por eso nos quedamos en un núcleo de factores robustos, interpretables y defendibles — y por eso puedes <em>ver</em> el porqué de cada puntuación.</p>
    </section>

    <!-- ==================== REFERENCIA TÉCNICA (separador) ==================== -->
    <div style="margin:32px 0 8px; padding:14px 18px; border-radius:10px; background:#33415522; border:1px dashed #475569;">
        <strong style="font-size:15px;">🔧 A partir de aquí: Referencia técnica (cómo está montada la app)</strong>
        <p style="margin:6px 0 0; font-size:13px; color:#94a3b8;">Lo anterior era <em>qué hace y cómo razona</em>. Esta parte es para quien quiera saber <em>cómo está construido</em> por dentro: arquitectura, stack, instalación y API. Si solo quieres usar FinTrack, no necesitas leerla.</p>
    </div>

    <!-- ==================== ARQUITECTURA DEL SISTEMA ==================== -->
    <section id="arquitectura" class="architecture-section">
        <h2>🏗️ Arquitectura del Sistema</h2>
        
        <p>FinTrack es una aplicación de <strong>arquitectura cliente-servidor</strong> que consta de un frontend web estático y un backend API en Python.</p>
        
        <!-- Diagrama Visual de Arquitectura -->
        <div class="architecture-diagram">
            <h3>📊 Diagrama General</h3>
            <pre class="diagram-box">
┌─────────────────────────────────────────────────────────────────────────────┐
│                              🌐 INTERNET                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  CoinGecko  │  │Yahoo Finance│  │    Groq     │  │  RSS Feeds  │        │
│  │  (Crypto)   │  │(Stocks/ETFs)│  │    (IA)     │  │  (Noticias) │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
└─────────┼────────────────┼────────────────┼────────────────┼───────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        🔧 BACKEND (FastAPI + Python)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         main.py (API REST)                          │   │
│  │   /api/portfolio  /api/positions  /api/news  /api/ai/chat          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ portfolio.py │ │coingecko.py  │ │yahoo_finance │ │   news.py    │       │
│  │  (Cálculos)  │ │  (Precios)   │ │   (Precios)  │ │  (Noticias)  │       │
│  └──────┬───────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
│         │                                                                   │
│  ┌──────▼───────────────────────────────────────────────────────────────┐  │
│  │                    📁 DATA (Almacenamiento Local)                    │  │
│  │  positions.csv (Cartera)  │  historical_values.json (Histórico)     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                               Puerto: 8000                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP/JSON
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      🎨 FRONTEND (HTML + CSS + JS)                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │  index.html  │ │  styles.css  │ │    app.js    │ │   pages.js   │       │
│  │  (Estructura)│ │   (Estilos)  │ │   (Lógica)   │ │ (Contenido)  │       │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                        │
│  │  Chart.js    │ │portfolio-mgr │ │ ai-advisor   │                        │
│  │  (Gráficos)  │ │  (Cartera)   │ │   (Chat IA)  │                        │
│  └──────────────┘ └──────────────┘ └──────────────┘                        │
│                            Puerto: 3000 (local) / Render (prod)            │
└─────────────────────────────────────────────────────────────────────────────┘
            </pre>
        </div>
        
        <!-- Servicios y APIs Externos -->
        <div class="services-section">
            <h3>🔌 APIs y Servicios Externos</h3>
            
            <table class="services-table" style="width: 100%; margin: 20px 0; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 2px solid var(--accent-primary);">
                        <th style="padding: 12px; text-align: left;">Servicio</th>
                        <th style="padding: 12px; text-align: left;">Uso</th>
                        <th style="padding: 12px; text-align: left;">Límites Gratis</th>
                        <th style="padding: 12px; text-align: left;">Coste</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid var(--border-primary);">
                        <td style="padding: 12px;">🪙 <strong>CoinGecko</strong></td>
                        <td style="padding: 12px;">Precios de criptomonedas (BTC, ETH, SOL...)</td>
                        <td style="padding: 12px;">10-50 peticiones/min</td>
                        <td style="padding: 12px; color: var(--success-color);">✅ Gratis</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-primary);">
                        <td style="padding: 12px;">📈 <strong>Yahoo Finance</strong></td>
                        <td style="padding: 12px;">Precios de acciones y ETFs</td>
                        <td style="padding: 12px;">~2000 peticiones/hora</td>
                        <td style="padding: 12px; color: var(--success-color);">✅ Gratis</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-primary);">
                        <td style="padding: 12px;">🤖 <strong>Groq API</strong></td>
                        <td style="padding: 12px;">Asesor IA (LLaMA 3.3 70B)</td>
                        <td style="padding: 12px;">14,400 peticiones/día</td>
                        <td style="padding: 12px; color: var(--success-color);">✅ Gratis</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-primary);">
                        <td style="padding: 12px;">📰 <strong>RSS Feeds</strong></td>
                        <td style="padding: 12px;">Noticias financieras</td>
                        <td style="padding: 12px;">Sin límite</td>
                        <td style="padding: 12px; color: var(--success-color);">✅ Gratis</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px;">☁️ <strong>Render.com</strong></td>
                        <td style="padding: 12px;">Hosting del backend y frontend</td>
                        <td style="padding: 12px;">750 horas/mes, spin-down tras 15min</td>
                        <td style="padding: 12px; color: var(--success-color);">✅ Gratis</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- Stack Tecnológico -->
        <div class="tech-stack">
            <h3>🛠️ Stack Tecnológico</h3>
            
            <div class="tech-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin: 20px 0;">
                <div class="tech-card" style="background: var(--bg-secondary); padding: 20px; border-radius: 12px; border-left: 4px solid #3776ab;">
                    <h4>🐍 Backend</h4>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong>Python 3.11</strong> - Lenguaje principal</li>
                        <li><strong>FastAPI</strong> - Framework web async</li>
                        <li><strong>Uvicorn</strong> - Servidor ASGI</li>
                        <li><strong>Pandas</strong> - Procesamiento de datos</li>
                        <li><strong>yfinance</strong> - API Yahoo Finance</li>
                        <li><strong>httpx</strong> - Cliente HTTP async</li>
                        <li><strong>feedparser</strong> - Parsing RSS</li>
                    </ul>
                </div>
                
                <div class="tech-card" style="background: var(--bg-secondary); padding: 20px; border-radius: 12px; border-left: 4px solid #f0db4f;">
                    <h4>🎨 Frontend</h4>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong>HTML5</strong> - Estructura</li>
                        <li><strong>CSS3</strong> - Estilos (variables CSS)</li>
                        <li><strong>JavaScript ES6+</strong> - Lógica</li>
                        <li><strong>Chart.js</strong> - Gráficos interactivos</li>
                        <li><strong>Fetch API</strong> - Peticiones HTTP</li>
                    </ul>
                </div>
                
                <div class="tech-card" style="background: var(--bg-secondary); padding: 20px; border-radius: 12px; border-left: 4px solid #06b6d4;">
                    <h4>💾 Almacenamiento</h4>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong>CSV</strong> - Posiciones de cartera</li>
                        <li><strong>JSON</strong> - Histórico y caché</li>
                        <li><strong>LocalStorage</strong> - Preferencias (futuro)</li>
                    </ul>
                </div>
                
                <div class="tech-card" style="background: var(--bg-secondary); padding: 20px; border-radius: 12px; border-left: 4px solid #46e3b7;">
                    <h4>☁️ Despliegue</h4>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li><strong>Render.com</strong> - Hosting gratuito</li>
                        <li><strong>GitHub</strong> - Control de versiones</li>
                        <li><strong>CI/CD</strong> - Deploy automático</li>
                    </ul>
                </div>
            </div>
        </div>
        
        <!-- Flujo de Datos -->
        <div class="data-flow">
            <h3>🔄 Flujo de Datos</h3>
            
            <h4>1. Carga del Dashboard</h4>
            <pre class="flow-diagram" style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; overflow-x: auto;">
Usuario abre web → Frontend carga → Llama GET /api/portfolio
                                              ↓
                        Backend lee positions.csv
                                              ↓
                        Obtiene precios de CoinGecko (crypto) + Yahoo Finance (stocks)
                                              ↓
                        Calcula: valor actual, P/L, métricas
                                              ↓
                        Responde JSON → Frontend renderiza gráficos y tablas
            </pre>
            
            <h4>2. Añadir Nueva Posición</h4>
            <pre class="flow-diagram" style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; overflow-x: auto;">
Usuario completa formulario → POST /api/positions {ticker, cantidad, precio}
                                              ↓
                        Backend valida datos
                                              ↓
                        Añade línea a positions.csv
                                              ↓
                        Responde éxito → Frontend actualiza vista
            </pre>
            
            <h4>3. Consulta al Asesor IA</h4>
            <pre class="flow-diagram" style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; overflow-x: auto;">
Usuario escribe pregunta → POST /api/ai/chat {pregunta, incluir_cartera}
                                              ↓
                        Backend obtiene datos de cartera (opcional)
                                              ↓
                        Llama a Groq API con contexto + pregunta
                                              ↓
                        Groq responde → Backend formatea → Frontend muestra respuesta
            </pre>
        </div>
        
        <!-- Estructura de Archivos -->
        <div class="file-structure">
            <h3>📁 Estructura de Archivos</h3>
            <pre style="background: var(--bg-tertiary); padding: 20px; border-radius: 8px; overflow-x: auto; font-size: 13px;">
personal-finance-dashboard/
├── 📁 backend/
│   ├── main.py                 # 🚀 API principal (FastAPI)
│   ├── requirements.txt        # 📦 Dependencias Python
│   ├── .env                    # 🔐 Variables de entorno (API keys)
│   ├── .python-version         # 🐍 Versión de Python
│   │
│   ├── 📁 services/            # Lógica de negocio
│   │   ├── portfolio.py        # 💼 Cálculos de cartera
│   │   ├── coingecko.py        # 🪙 Precios crypto
│   │   ├── yahoo_finance.py    # 📈 Precios stocks/ETFs
│   │   ├── exchange_rate.py    # 💱 Conversión de divisas
│   │   └── news.py             # 📰 Noticias RSS
│   │
│   └── 📁 data/                # Almacenamiento
│       ├── positions.csv       # 📊 Tu cartera
│       └── historical_values.json  # 📈 Histórico
│
├── 📁 frontend/
│   ├── index.html              # 🏠 Página principal
│   │
│   ├── 📁 css/
│   │   └── styles.css          # 🎨 Estilos
│   │
│   └── 📁 js/
│       ├── app.js              # ⚙️ Lógica principal
│       ├── pages.js            # 📄 Contenido de páginas
│       ├── portfolio-manager.js # 💼 Gestión cartera
│       ├── ai-advisor.js       # 🤖 Chat IA
│       ├── news.js             # 📰 Noticias
│       └── asset-analysis.js   # 📊 Análisis activos
│
├── render.yaml                 # ☁️ Configuración Render
├── .gitignore                  # 🚫 Archivos ignorados
└── README.md                   # 📖 Documentación
            </pre>
        </div>
        
        <!-- Caché y Rendimiento -->
        <div class="cache-section">
            <h3>⚡ Caché y Rendimiento</h3>
            
            <table style="width: 100%; margin: 20px 0; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 2px solid var(--accent-primary);">
                        <th style="padding: 12px; text-align: left;">Dato</th>
                        <th style="padding: 12px; text-align: left;">Tiempo de Caché</th>
                        <th style="padding: 12px; text-align: left;">Razón</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid var(--border-primary);">
                        <td style="padding: 12px;">Precios Crypto (CoinGecko)</td>
                        <td style="padding: 12px;">10 minutos</td>
                        <td style="padding: 12px;">Evitar rate limiting (50 req/min)</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-primary);">
                        <td style="padding: 12px;">Precios Stocks (Yahoo)</td>
                        <td style="padding: 12px;">15 minutos</td>
                        <td style="padding: 12px;">Mercados se actualizan cada 15min</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--border-primary);">
                        <td style="padding: 12px;">Histórico de activos</td>
                        <td style="padding: 12px;">30 minutos</td>
                        <td style="padding: 12px;">Datos diarios, no cambian frecuentemente</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px;">Noticias RSS</td>
                        <td style="padding: 12px;">30 minutos</td>
                        <td style="padding: 12px;">Las noticias no cambian cada segundo</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- Seguridad -->
        <div class="security-section">
            <h3>🔒 Seguridad</h3>
            
            <div class="security-info" style="background: var(--bg-secondary); padding: 20px; border-radius: 12px; margin: 20px 0;">
                <h4>Estado Actual</h4>
                <ul style="padding-left: 20px;">
                    <li>✅ Datos almacenados localmente (no en la nube)</li>
                    <li>✅ API keys en variables de entorno (.env)</li>
                    <li>✅ No se almacenan contraseñas de brokers</li>
                    <li>✅ Conexiones HTTPS en producción</li>
                    <li>⚠️ Sin autenticación (cualquiera con la URL puede ver/editar)</li>
                </ul>
                
                <h4 style="margin-top: 15px;">Recomendaciones Futuras</h4>
                <ul style="padding-left: 20px;">
                    <li>🔜 Añadir autenticación OAuth (Google/GitHub)</li>
                    <li>🔜 Encriptar datos sensibles</li>
                    <li>🔜 Añadir rate limiting propio</li>
                </ul>
            </div>
        </div>
    </section>

    <section id="inicio-rapido">
        <h2>1. Inicio Rápido</h2>
        
        <h3>Requisitos</h3>
        <ul>
            <li>Python 3.10 o superior</li>
            <li>Navegador web moderno (Chrome, Firefox, Safari, Edge)</li>
            <li>Conexión a internet (para obtener precios)</li>
        </ul>
        
        <h3>Instalación</h3>
        <pre><code># 1. Navegar al directorio del proyecto
cd ~/personal-finance-dashboard

# 2. Crear entorno virtual
cd backend
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\\Scripts\\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Iniciar el servidor
python main.py</code></pre>
        
        <h3>Acceder al Dashboard</h3>
        <p>Abre dos terminales:</p>
        
        <pre><code># Terminal 1: Backend (API)
cd backend && source venv/bin/activate && python main.py
# Disponible en: http://localhost:8000

# Terminal 2: Frontend
cd frontend && python3 -m http.server 3000
# Disponible en: http://localhost:3000</code></pre>
    </section>

    <section id="configuracion">
        <h2>2. Configuración</h2>
        
        <h3>Archivo de Posiciones</h3>
        <p>Tus posiciones se almacenan en <code>backend/data/positions.csv</code>:</p>
        
        <pre><code>ticker,quantity,avg_price,type,currency,broker
AAPL,10,145,stock,USD,TradeRepublic
MSFT,5,280,stock,USD,MyInvestor
VWCE.DE,12,98,etf,EUR,MyInvestor
BTC,0.3,25000,crypto,USD,Kraken
ETH,2,1800,crypto,USD,Kraken</code></pre>
        
        <h3>Campos del CSV</h3>
        <table style="width: 100%; margin: 20px 0;">
            <thead>
                <tr style="border-bottom: 2px solid var(--border-secondary);">
                    <th style="text-align: left; padding: 10px;">Campo</th>
                    <th style="text-align: left; padding: 10px;">Descripción</th>
                    <th style="text-align: left; padding: 10px;">Ejemplo</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>ticker</code></td>
                    <td style="padding: 10px;">Símbolo del activo</td>
                    <td style="padding: 10px;">AAPL, BTC, VWCE.DE</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>quantity</code></td>
                    <td style="padding: 10px;">Cantidad de unidades</td>
                    <td style="padding: 10px;">10, 0.5, 100</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>avg_price</code></td>
                    <td style="padding: 10px;">Precio medio de compra</td>
                    <td style="padding: 10px;">145.50</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>type</code></td>
                    <td style="padding: 10px;">Tipo de activo</td>
                    <td style="padding: 10px;">stock, etf, crypto</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>currency</code></td>
                    <td style="padding: 10px;">Moneda del activo</td>
                    <td style="padding: 10px;">USD, EUR</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><code>broker</code></td>
                    <td style="padding: 10px;">Nombre del broker</td>
                    <td style="padding: 10px;">TradeRepublic, MyInvestor</td>
                </tr>
            </tbody>
        </table>
        
        <h3>Tickers Especiales</h3>
        <ul>
            <li><strong>Acciones europeas:</strong> Añadir sufijo del mercado (VWCE<strong>.DE</strong>, SAP<strong>.DE</strong>)</li>
            <li><strong>Acciones españolas:</strong> Ticker + .MC (SAN<strong>.MC</strong>, ITX<strong>.MC</strong>)</li>
            <li><strong>Criptomonedas:</strong> Usar símbolo estándar (BTC, ETH, SOL)</li>
        </ul>
        
        <h3>Variables de Entorno (Opcional)</h3>
        <p>Crea un archivo <code>.env</code> en <code>backend/</code>:</p>
        <pre><code># Alpha Vantage (backup para acciones)
ALPHA_VANTAGE_API_KEY=tu_api_key

# Cambiar moneda base (por defecto EUR)
BASE_CURRENCY=EUR</code></pre>
    </section>

    <section id="añadir-posiciones">
        <h2>3. Añadir Posiciones</h2>
        
        <h3>Método 1: Editar CSV Manualmente</h3>
        <p>Abre <code>backend/data/positions.csv</code> con cualquier editor de texto o Excel y añade nuevas líneas.</p>
        
        <h3>Método 2: API REST</h3>
        <pre><code># Añadir nueva posición
curl -X POST "http://localhost:8000/api/positions" \\
  -H "Content-Type: application/json" \\
  -d '{
    "ticker": "GOOGL",
    "quantity": 5,
    "avg_price": 140,
    "type": "stock",
    "currency": "USD",
    "broker": "TradeRepublic"
  }'

# Actualizar posición existente
curl -X PUT "http://localhost:8000/api/positions/GOOGL" \\
  -H "Content-Type: application/json" \\
  -d '{"quantity": 10, "avg_price": 135}'

# Eliminar posición
curl -X DELETE "http://localhost:8000/api/positions/GOOGL"</code></pre>
        
        <h3>Método 3: Interfaz de Transacciones</h3>
        <p>Usa la página de <strong>Transacciones</strong> en el dashboard para registrar compras y ventas que actualizarán automáticamente tus posiciones.</p>
    </section>

    <section id="funcionalidades">
        <h2>4. Funcionalidades</h2>
        
        <h3>📊 Dashboard Principal</h3>
        <ul>
            <li>Valor total de cartera en tiempo real</li>
            <li>Rentabilidad diaria y acumulada</li>
            <li>KPIs: CAGR, Drawdown, Volatilidad, Sharpe</li>
            <li>Gráfico de evolución histórica</li>
            <li>Distribución por tipo, broker y divisa</li>
            <li>Tabla de posiciones ordenable y filtrable</li>
        </ul>
        
        <h3>📈 Análisis</h3>
        <ul>
            <li>Comparativa con benchmark (S&P 500)</li>
            <li>Distribución de riesgo</li>
            <li>Top movers del mes</li>
            <li>Estadísticas de rendimiento</li>
        </ul>
        
        <h3>💸 Transacciones</h3>
        <ul>
            <li>Registro de compras, ventas y dividendos</li>
            <li>Filtrado por fecha y tipo</li>
            <li>Historial completo de operaciones</li>
        </ul>
        
        <h3>🎯 Objetivos</h3>
        <ul>
            <li>Crear metas financieras personalizadas</li>
            <li>Seguimiento visual del progreso</li>
            <li>Proyección de patrimonio futuro</li>
        </ul>
        
        <h3>🔔 Alertas</h3>
        <ul>
            <li>Alertas de precio (mayor/menor que X)</li>
            <li>Alertas de cambio porcentual diario</li>
            <li>Notificaciones cuando se disparan</li>
        </ul>
        
        <h3>🧮 Calculadoras</h3>
        <ul>
            <li><strong>Interés Compuesto:</strong> Proyección de crecimiento</li>
            <li><strong>FIRE:</strong> Número objetivo para independencia financiera</li>
            <li><strong>DCA:</strong> Simulación de inversión periódica</li>
            <li><strong>Dividendos:</strong> Estimación de ingresos pasivos</li>
        </ul>
    </section>

    <section id="api">
        <h2>5. API Reference</h2>
        
        <p>La documentación completa de la API está disponible en: <code>http://localhost:8000/docs</code></p>
        
        <h3>Endpoints Principales</h3>
        
        <table style="width: 100%; margin: 20px 0;">
            <thead>
                <tr style="border-bottom: 2px solid var(--border-secondary);">
                    <th style="padding: 10px;">Método</th>
                    <th style="padding: 10px;">Endpoint</th>
                    <th style="padding: 10px;">Descripción</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>GET</code></td>
                    <td style="padding: 10px;"><code>/api/portfolio</code></td>
                    <td style="padding: 10px;">Cartera completa con métricas</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>GET</code></td>
                    <td style="padding: 10px;"><code>/api/portfolio/history</code></td>
                    <td style="padding: 10px;">Histórico de valores</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>GET</code></td>
                    <td style="padding: 10px;"><code>/api/positions</code></td>
                    <td style="padding: 10px;">Lista de posiciones</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>POST</code></td>
                    <td style="padding: 10px;"><code>/api/positions</code></td>
                    <td style="padding: 10px;">Añadir posición</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>PUT</code></td>
                    <td style="padding: 10px;"><code>/api/positions/{ticker}</code></td>
                    <td style="padding: 10px;">Actualizar posición</td>
                </tr>
                <tr style="border-bottom: 1px solid var(--border-primary);">
                    <td style="padding: 10px;"><code>DELETE</code></td>
                    <td style="padding: 10px;"><code>/api/positions/{ticker}</code></td>
                    <td style="padding: 10px;">Eliminar posición</td>
                </tr>
                <tr>
                    <td style="padding: 10px;"><code>POST</code></td>
                    <td style="padding: 10px;"><code>/api/refresh</code></td>
                    <td style="padding: 10px;">Forzar actualización</td>
                </tr>
            </tbody>
        </table>
    </section>

    <section id="faq">
        <h2>6. Preguntas Frecuentes</h2>
        
        <h3>¿Con qué frecuencia se actualizan los precios?</h3>
        <p>Los precios se cachean durante 15 minutos para evitar exceder los límites de las APIs gratuitas. Puedes forzar una actualización con el botón de refresh.</p>
        
        <h3>¿Por qué mi ticker no se encuentra?</h3>
        <ul>
            <li>Verifica que el símbolo es correcto</li>
            <li>Para acciones europeas, añade el sufijo del mercado (.DE, .MC, .PA, etc.)</li>
            <li>Para criptomonedas, usa el símbolo estándar (BTC, no Bitcoin)</li>
        </ul>
        
        <h3>¿Cómo cambio la moneda base?</h3>
        <p>Edita <code>backend/main.py</code> y cambia <code>base_currency="EUR"</code> a tu moneda preferida.</p>
        
        <h3>¿Mis datos son privados?</h3>
        <p>Sí. Todos los datos se almacenan localmente en tu ordenador. No se envía información a servidores externos más allá de las consultas de precios a Yahoo Finance y CoinGecko.</p>
        
        <h3>¿Puedo exportar mis datos?</h3>
        <p>Sí. Usa el botón de exportar (📥) en la tabla de posiciones para descargar un CSV, o accede directamente a los archivos en <code>backend/data/</code>.</p>
        
        <h3>¿Cómo añado un nuevo broker?</h3>
        <p>Simplemente escribe el nombre del nuevo broker en el campo "broker" del CSV o al crear una transacción. El sistema lo reconocerá automáticamente.</p>
    </section>

    <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:24px;">
        <a href="#" onclick="document.querySelector('[data-page=learn]').click(); return false;" style="flex:1; min-width:200px; background:#6366f114; border:1px solid #6366f144; border-radius:10px; padding:14px 18px; text-decoration:none; color:inherit;">
            <strong>← Volver a Aprender</strong>
            <p style="margin:6px 0 0; font-size:13px; color:#94a3b8;">Repasa los fundamentos y las métricas.</p>
        </a>
        <a href="#" onclick="document.querySelector('[data-page=polymarket]').click(); return false;" style="flex:1; min-width:200px; background:#00d4aa14; border:1px solid #00d4aa44; border-radius:10px; padding:14px 18px; text-decoration:none; color:inherit;">
            <strong>Siguiente: Polymarket Lab →</strong>
            <p style="margin:6px 0 0; font-size:13px; color:#94a3b8;">La visión: hacia un asistente autónomo.</p>
        </a>
    </div>
</div>
    `
};

/**
 * Initialize page navigation
 */
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const pages = document.querySelectorAll('.page');
    const pageTitle = document.getElementById('pageTitle');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const pageName = item.dataset.page;
            
            // Update active nav item
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // Show corresponding page
            pages.forEach(page => page.classList.remove('active'));
            const targetPage = document.getElementById(`page-${pageName}`);
            if (targetPage) {
                targetPage.classList.add('active');
            }
            
            // Update page title
            const titles = {
                'dashboard': 'Dashboard',
                'analysis': 'Análisis',
                'transactions': 'Transacciones',
                'portfolio-manager': 'Gestionar Cartera',
                'goals': 'Objetivos',
                'alerts': 'Alertas',
                'calculators': 'Calculadoras',
                'ai-advisor': 'Asesor IA',
                'news': 'Noticias',
                'opportunities': 'Oportunidades',
                'backtest': 'Backtest',
                'polymarket': 'Polymarket Lab',
                'learn': 'Aprender',
                'docs': 'Documentación'
            };
            pageTitle.textContent = titles[pageName] || 'Dashboard';
            
            // Load dynamic content for pages
            if (pageName === 'learn') {
                loadLearnPage(targetPage);
            }
            if (pageName === 'docs') {
                targetPage.innerHTML = pageContent.docs;
            }
            if (pageName === 'news' && window.renderNews) {
                window.renderNews();
            }
            if (pageName === 'portfolio-manager' && window.loadManagerPositions) {
                window.loadManagerPositions();
            }
            if (pageName === 'analysis' && window.initAssetAnalysis) {
                window.initAssetAnalysis();
            }
            
            // Close sidebar on mobile
            if (window.innerWidth <= 900) {
                document.querySelector('.sidebar').classList.remove('open');
            }
        });
    });
    
    // Mobile menu toggle
    const menuToggle = document.getElementById('menuToggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            document.querySelector('.sidebar').classList.toggle('open');
        });
    }
}

/**
 * Initialize modals
 */
function initModals() {
    // Transaction Modal
    const transactionModal = document.getElementById('transactionModal');
    const btnAddTransaction = document.getElementById('btnAddTransaction');
    const closeTransactionModal = document.getElementById('closeTransactionModal');
    const cancelTransaction = document.getElementById('cancelTransaction');
    
    if (btnAddTransaction) {
        btnAddTransaction.addEventListener('click', () => {
            transactionModal.classList.add('active');
            // Set default date to today
            const dateInput = transactionModal.querySelector('input[name="date"]');
            if (dateInput) {
                dateInput.value = new Date().toISOString().split('T')[0];
            }
        });
    }
    
    if (closeTransactionModal) {
        closeTransactionModal.addEventListener('click', () => {
            transactionModal.classList.remove('active');
        });
    }
    
    if (cancelTransaction) {
        cancelTransaction.addEventListener('click', () => {
            transactionModal.classList.remove('active');
        });
    }
    
    // Alert Modal
    const alertModal = document.getElementById('alertModal');
    const btnAddAlert = document.getElementById('btnAddAlert');
    const closeAlertModal = document.getElementById('closeAlertModal');
    const cancelAlert = document.getElementById('cancelAlert');
    
    if (btnAddAlert) {
        btnAddAlert.addEventListener('click', () => {
            alertModal.classList.add('active');
        });
    }
    
    if (closeAlertModal) {
        closeAlertModal.addEventListener('click', () => {
            alertModal.classList.remove('active');
        });
    }
    
    if (cancelAlert) {
        cancelAlert.addEventListener('click', () => {
            alertModal.classList.remove('active');
        });
    }
    
    // Close modals on outside click
    [transactionModal, alertModal].forEach(modal => {
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('active');
                }
            });
        }
    });
}

/**
 * Initialize projection chart for goals page
 */
function initProjectionChart() {
    const ctx = document.getElementById('projectionChart');
    if (!ctx) return;
    
    const updateBtn = document.getElementById('updateProjection');
    
    function createProjection() {
        const monthly = parseFloat(document.getElementById('monthlyContribution')?.value) || 500;
        const expectedReturn = parseFloat(document.getElementById('expectedReturn')?.value) / 100 || 0.07;
        const currentValue = parseFloat(document.getElementById('totalValue')?.textContent?.replace(/[^0-9.-]+/g, '')) || 40000;
        
        const years = 20;
        const labels = [];
        const values = [];
        let value = currentValue;
        const monthlyReturn = expectedReturn / 12;
        
        for (let year = 0; year <= years; year++) {
            labels.push(2026 + year);
            values.push(Math.round(value));
            
            // Calculate next year's value
            for (let month = 0; month < 12; month++) {
                value = value * (1 + monthlyReturn) + monthly;
            }
        }
        
        if (window.projectionChart && typeof window.projectionChart.destroy === 'function') {
            window.projectionChart.destroy();
        }
        
        window.projectionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Proyección',
                    data: values,
                    borderColor: '#00d4aa',
                    backgroundColor: 'rgba(0, 212, 170, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        ticks: {
                            callback: value => value.toLocaleString('es-ES') + ' €'
                        }
                    }
                }
            }
        });
    }
    
    createProjection();
    
    if (updateBtn) {
        updateBtn.addEventListener('click', createProjection);
    }
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Export for global use
window.showToast = showToast;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initModals();
    
    // Initialize projection chart when goals page is shown
    setTimeout(initProjectionChart, 1000);
});

