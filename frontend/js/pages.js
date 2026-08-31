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
        const response = await fetch('pages/learn.html?v=20260831b', { cache: 'no-store' });
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

/**
 * Fetch the real, current scorecard + systematic-engine status and fill in
 * the "Estado real ahora mismo" boxes in Documentación. Live on every visit
 * — never hardcoded, so it can't go stale like a written-in-prose number would.
 */
async function loadLiveDocsStatus() {
    const API = window.API_BASE_URL || 'http://localhost:8000/api';

    const autoEl = document.getElementById('liveAutoentrenamientoContent');
    if (autoEl) {
        try {
            const r = await fetch(`${API}/scorecard`, { cache: 'no-store' });
            const d = await r.json();
            const m1 = d.horizons?.ret_1m;
            const gate = d.feedback_gate || { by_approach: {}, by_conviction: {} };
            const gatedBuckets = [...Object.entries(gate.by_approach || {}), ...Object.entries(gate.by_conviction || {})]
                .filter(([, v]) => v.gated);
            let html = `<strong>${d.total_recommendations_tracked ?? '—'}</strong> recomendaciones registradas · `
                + `<strong>${d.evaluated_any ?? 0}</strong> ya evaluadas a 1 mes`;
            if (m1?.return) {
                html += ` (rentabilidad media ${m1.return.avg >= 0 ? '+' : ''}${m1.return.avg}%, ${m1.return.hit_rate_pct}% de aciertos; `
                    + `frente a su benchmark: ${m1.alpha_vs_benchmark.hit_rate_pct}% de aciertos)`;
            }
            html += `.<br>A 3 meses (el horizonte que de verdad activa el autoentrenamiento): `
                + `<strong>${d.horizons?.ret_3m?.return?.n ?? 0}</strong> evaluadas todavía.<br>`;
            html += gatedBuckets.length
                ? `<strong style="color:#00d4aa;">${gatedBuckets.length} enfoque(s) ya han cruzado el filtro anti-ruido</strong> y están influyendo en la convicción de nuevas ideas.`
                : `El filtro anti-ruido sigue <strong>cerrado</strong> para todos los enfoques — cero influencia real todavía sobre las recomendaciones.`;
            autoEl.innerHTML = html;
        } catch (err) {
            autoEl.innerHTML = 'No se pudo consultar el scorecard en vivo ahora mismo — inténtalo recargando la página.';
        }
    }

    const sisEl = document.getElementById('liveSistematicoContent');
    if (sisEl) {
        try {
            const r = await fetch(`${API}/systematic/paper/report`, { cache: 'no-store' });
            const d = await r.json();
            const rd = d.readiness || {};
            const pct = (v) => (typeof v === 'number' ? `${v >= 0 ? '+' : ''}${v}%` : '—');
            if (typeof d.days !== 'number') {
                // No marks yet at all — a genuinely different (minimal) response shape.
                sisEl.innerHTML = `Todavía sin histórico que mostrar (${d.status || 'aún no ha empezado a marcar NAV'}). `
                    + `Veredicto: <strong style="color:#f59e0b;">${rd.verdict || rd.note || '—'}</strong>`;
            } else {
                sisEl.innerHTML = `<strong>${d.days}</strong> días en papel (de los 56 mínimos), <strong>${d.marks ?? '—'}</strong> marcas diarias.<br>`
                    + `Rentabilidad: <strong>${pct(d.return_pct)}</strong> vs <strong>${pct(d.benchmark_return_pct)}</strong> del benchmark `
                    + `(alpha ${pct(d.alpha_pct)}). Sharpe ${d.sharpe ?? '—'} vs ${d.benchmark_sharpe ?? '—'} del benchmark.<br>`
                    + `PSR: <strong>${Math.round((d.psr ?? 0) * 100)}%</strong> (necesita ≥75%).<br>`
                    + `Veredicto del propio sistema: <strong style="color:${rd.ready ? '#00d4aa' : '#f59e0b'};">${rd.verdict ?? '—'}</strong>`;
            }
        } catch (err) {
            sisEl.innerHTML = 'No se pudo consultar el estado en vivo ahora mismo — inténtalo recargando la página.';
        }
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
        <p style="font-size:13px; color:#94a3b8; margin:0 0 8px;">Léelo de arriba abajo: va de <em>qué es</em> → <em>cómo se usa</em> → <em>cómo funciona por dentro</em> → <em>detalle técnico</em>. Cada tarjeta lleva una etiqueta de nivel para que sepas qué esperar antes de entrar.</p>
        <div class="toc-grid">
            <p class="toc-category-label">Empezar aquí</p>
            <a href="#que-es" class="toc-card">
                <span class="toc-icon">🎯</span>
                <span class="toc-title">Qué es FinTrack y la visión</span>
                <span class="toc-desc">Qué hace por ti la app en una frase, y qué NO hace (no predice, no ordena comprar).</span>
                <span class="toc-badge nivel-basico">Básico</span>
            </a>
            <a href="#guia-uso" class="toc-card">
                <span class="toc-icon">🧭</span>
                <span class="toc-title">Guía de uso: pestaña por pestaña</span>
                <span class="toc-desc">Qué hace cada sección de la barra lateral y cuándo usarla.</span>
                <span class="toc-badge nivel-basico">Básico</span>
            </a>
            <a href="#el-cerebro" class="toc-card">
                <span class="toc-icon">🧠</span>
                <span class="toc-title">El cerebro: cómo descubre y recomienda</span>
                <span class="toc-desc">El recorrido paso a paso: de escanear el mercado a explicarte una idea concreta.</span>
                <span class="toc-badge nivel-intermedio">Intermedio</span>
            </a>

            <p class="toc-category-label">Cómo razona (los algoritmos)</p>
            <a href="#novedades" class="toc-card">
                <span class="toc-icon">🆕</span>
                <span class="toc-title">Novedades (asistente autónomo con IA)</span>
                <span class="toc-desc">Qué ha cambiado últimamente en el motor y por qué.</span>
                <span class="toc-badge nivel-basico">Básico</span>
            </a>
            <a href="#algoritmos" class="toc-card">
                <span class="toc-icon">🔬</span>
                <span class="toc-title">Cómo funcionan nuestros algoritmos</span>
                <span class="toc-desc">Los 10 "jueces" estadísticos que puntúan cada activo, con fórmulas y ejemplos numéricos.</span>
                <span class="toc-badge nivel-avanzado">Avanzado</span>
            </a>
            <a href="#autoentrenamiento" class="toc-card">
                <span class="toc-icon">🎯</span>
                <span class="toc-title">Autoentrenamiento</span>
                <span class="toc-desc">Cómo (y cuándo, con qué condiciones anti-ruido) el motor aprende de sus propios aciertos y fallos.</span>
                <span class="toc-badge nivel-intermedio">Intermedio</span>
            </a>
            <a href="#motor-sistematico" class="toc-card">
                <span class="toc-icon">📈</span>
                <span class="toc-title">El motor sistemático: cartera en papel</span>
                <span class="toc-desc">La segunda cartera 100% automática que se prueba sin dinero real hasta que supere un examen estadístico.</span>
                <span class="toc-badge nivel-avanzado">Avanzado</span>
            </a>
            <a href="#que-ia-usamos" class="toc-card">
                <span class="toc-icon">🤖</span>
                <span class="toc-title">Qué IA usamos y por qué</span>
                <span class="toc-desc">Gemini, Groq, y los tres candados técnicos que evitan que la IA se invente cosas.</span>
                <span class="toc-badge nivel-basico">Básico</span>
            </a>
            <a href="#glosario" class="toc-card">
                <span class="toc-icon">📔</span>
                <span class="toc-title">Glosario completo</span>
                <span class="toc-desc">Todos los términos técnicos de esta página (Sharpe, PSR, RSI, alpha...) en una sola tabla A-Z.</span>
                <span class="toc-badge nivel-basico">Básico</span>
            </a>

            <p class="toc-category-label">Referencia técnica (cómo está montado)</p>
            <a href="#arquitectura" class="toc-card">
                <span class="toc-icon">🏗️</span>
                <span class="toc-title">Arquitectura del Sistema</span>
                <span class="toc-desc">Diagrama completo de frontend, backend y servicios externos.</span>
                <span class="toc-badge nivel-tecnico">Técnico</span>
            </a>
            <a href="#inicio-rapido" class="toc-card">
                <span class="toc-icon">⚡</span>
                <span class="toc-title">Inicio Rápido</span>
                <span class="toc-desc">Cómo levantar el proyecto en local desde cero.</span>
                <span class="toc-badge nivel-tecnico">Técnico</span>
            </a>
            <a href="#configuracion" class="toc-card">
                <span class="toc-icon">⚙️</span>
                <span class="toc-title">Configuración</span>
                <span class="toc-desc">Variables de entorno y ajustes disponibles.</span>
                <span class="toc-badge nivel-tecnico">Técnico</span>
            </a>
            <a href="#añadir-posiciones" class="toc-card">
                <span class="toc-icon">➕</span>
                <span class="toc-title">Añadir Posiciones</span>
                <span class="toc-desc">Cómo dar de alta un activo o broker nuevo en tu cartera.</span>
                <span class="toc-badge nivel-tecnico">Técnico</span>
            </a>
            <a href="#funcionalidades" class="toc-card">
                <span class="toc-icon">🧩</span>
                <span class="toc-title">Funcionalidades</span>
                <span class="toc-desc">Listado completo de lo que la app puede hacer hoy.</span>
                <span class="toc-badge nivel-tecnico">Técnico</span>
            </a>
            <a href="#api" class="toc-card">
                <span class="toc-icon">🔌</span>
                <span class="toc-title">API Reference</span>
                <span class="toc-desc">Endpoints REST disponibles, para quien quiera consultar los datos crudos.</span>
                <span class="toc-badge nivel-tecnico">Técnico</span>
            </a>
            <a href="#faq" class="toc-card">
                <span class="toc-icon">❓</span>
                <span class="toc-title">Preguntas Frecuentes</span>
                <span class="toc-desc">Dudas comunes sobre seguridad, datos y coste del proyecto.</span>
                <span class="toc-badge nivel-basico">Básico</span>
            </a>
        </div>
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

    <!-- ==================== AUTOENTRENAMIENTO ==================== -->
    <section id="autoentrenamiento">
        <h2>🎯 Autoentrenamiento: cómo (y cuándo) aprende de sus aciertos</h2>
        <p><strong>Empezando desde cero — qué significa "autoentrenar" aquí:</strong> no es que una red neuronal reajuste sus propios números por dentro (eso es lo que mucha gente imagina al oír "IA que aprende", y aquí no funciona así). Es algo más simple y más verificable: el sistema <strong>apunta cada recomendación que hace</strong>, espera a ver <strong>qué pasó de verdad</strong> con el precio después, y usa ese resultado real para ser más o menos "confiado" la próxima vez que proponga algo parecido. Como un alumno que lleva la cuenta de en qué tipo de examen suele fallar más, en vez de cambiar de cerebro.</p>

        <div class="info-box" id="liveAutoentrenamientoBox">
            <strong>📡 Estado real ahora mismo</strong> <span style="font-size:11px; color:#94a3b8;">(se consulta en vivo cada vez que abres esta página — no son cifras fijas)</span>
            <p id="liveAutoentrenamientoContent" style="margin-top:8px;">Cargando datos reales del scorecard…</p>
        </div>

        <h3>Paso a paso, con un ejemplo (fechas inventadas para que se vea claro)</h3>
        <p>Cada recomendación que ves en Oportunidades se guarda con tres datos: <strong>la fecha</strong>, <strong>su enfoque</strong> (MOMENTUM = "esto está subiendo con fuerza" o VALOR = "esto está barato pero es de calidad" — ver <a href="#algoritmos">Cómo funcionan nuestros algoritmos</a>) y <strong>su convicción</strong> (alta/media/baja). Un proceso automático revisa cada día las recomendaciones antiguas y, si ha pasado suficiente tiempo, calcula <strong>qué rentabilidad habría dado de verdad</strong> esa idea a 1, 3 y 6 meses, comparada con su propio índice de referencia (por ejemplo, un ETF de semiconductores se compara contra el índice de semiconductores, no contra el IBEX). A este informe de resultados reales lo llamamos <em>scorecard</em> ("boletín de notas"), y es público — lo puedes consultar tú mismo entrando a <code>fintrack-front.onrender.com/api/scorecard</code> desde el navegador.</p>

        <div class="example-box">
            <h4>Ejemplo: imagina que hoy es 1 de octubre</h4>
            <table class="data-table">
                <thead>
                    <tr><th>Recomendación creada</th><th>Enfoque</th><th>Edad hoy</th><th>¿Tiene ya 3 meses (90 días)?</th></tr>
                </thead>
                <tbody>
                    <tr><td>25 julio</td><td>Momentum</td><td>68 días</td><td>No — le faltan 22 días</td></tr>
                    <tr><td>10 agosto</td><td>Momentum</td><td>52 días</td><td>No</td></tr>
                    <tr><td>3 septiembre</td><td>Momentum</td><td>28 días</td><td>No</td></tr>
                    <tr><td>20 abril (6 meses antes)</td><td>Momentum</td><td>164 días</td><td>Sí</td></tr>
                </tbody>
            </table>
            <p>De estas 4, solo <strong>1 sola</strong> ya tiene 3 meses cumplidos. Para activar el autoentrenamiento hacen falta <strong>al menos 30</strong> así de "maduras" — y encima, veremos ahora por qué ni con 30 basta siempre.</p>
        </div>

        <div class="formula-box">
            <p><strong>La regla exacta que lo protege de sí mismo (las dos condiciones deben cumplirse A LA VEZ):</strong></p>
            <ol style="text-align:left;">
                <li><strong>Al menos 30 recomendaciones</strong> de ese enfoque ya "maduras" (con 90+ días de vida, para poder medir su resultado a 3 meses).</li>
                <li>Esas 30+ recomendaciones deben tener <strong>fechas de creación repartidas en al menos 90 días</strong> entre la más antigua y la más reciente del grupo.</li>
            </ol>
            <p>Si falla cualquiera de las dos, el resultado de ese enfoque se descarta <strong>por completo</strong> — no "se usa un poco", se ignora del todo, como si no existiera.</p>
        </div>

        <h3>¿Por qué la condición 2 (el rango de 90 días) y no solo contar 30?</h3>
        <p>Porque 30 recomendaciones podrían, sin la condición 2, estar todas creadas la misma semana:</p>
        <div class="comparison-box">
            <div class="comparison-item">
                <h4>Caso A — sin rango</h4>
                <p>30 recomendaciones, todas de <strong>la primera semana de marzo</strong>.<br>n = 30 ✔ — pero rango de fechas ≈ 7 días ✘</p>
                <div class="result negative">SE DESCARTA — podría ser solo que "marzo fue un mes raro para la bolsa", no que MOMENTUM funcione en general.</div>
            </div>
            <div class="comparison-item">
                <h4>Caso B — con rango</h4>
                <p>30 recomendaciones repartidas <strong>entre enero y julio</strong> (180 días).<br>n = 30 ✔ y rango = 180 días ≥ 90 ✔</p>
                <div class="result positive">SE USA — ha visto meses buenos y malos, subidas y bajadas: puesto a prueba en condiciones distintas.</div>
            </div>
        </div>
        <p>Es la misma lógica de "no juzgues un método de estudio por un solo examen": si un alumno saca un 9 en el único examen que ha hecho, no sabes si es bueno estudiando o si el examen era fácil ese día. Necesitas verlo en varios exámenes, en fechas distintas, con temarios distintos.</p>

        <h3>Entonces, ¿cuándo se activa de verdad?</h3>
        <p>El sistema empezó a rastrear recomendaciones reales hace relativamente poco. Aunque ya haya cientos registradas, no basta con que la primera cumpla 3 meses — hacen falta <strong>dos plazos, uno detrás del otro</strong>:</p>
        <div class="formula-box">
            <ol style="text-align:left;">
                <li>Que la recomendación <strong>más antigua</strong> registrada cumpla sus 90 días.</li>
                <li>Que, ADEMÁS, haya otras 29+ recomendaciones creadas hasta 90 días después de esa primera que <strong>también</strong> hayan cumplido ya sus propios 90 días.</li>
            </ol>
            <p>Sumando ambos plazos, la primera vez que el gate puede abrirse ronda los <strong>5-6 meses desde que se empezó a rastrear en serio</strong> — no antes, por diseño, sea cual sea el volumen de recomendaciones que se acumulen mientras tanto.</p>
        </div>
        <p>Mientras tanto (y va a ser así durante meses), el sistema funciona <strong>exactamente igual que siempre</strong> — motor cuantitativo + noticias + IA que explica, sin ningún ajuste — y el propio <em>scorecard</em> lo dice explícitamente ("insuficiente, sin conclusión") en vez de fingir que ya sabe algo que todavía no sabe.</p>
        <p><strong>Qué NO hace, ni cuando se active:</strong> no toca las fórmulas del motor cuantitativo — los pesos de momentum/valor de <a href="#algoritmos">la sección de algoritmos</a> siguen siendo fijos y auditables, siempre los mismos. El único efecto posible, y solo para un enfoque que ya haya superado el filtro con un resultado real negativo, es que la próxima idea de ese enfoque se presente con la convicción un escalón más baja (de "alta" a "media", por ejemplo) — nunca al revés hacia arriba de forma automática, y nunca sobre qué activos entran al ranking.</p>

        <h3>🧮 Cómo se calcula "qué habría pasado de verdad" — paso a paso con números</h3>
        <p>Cuando una recomendación de un ETF cumple 3 meses, el sistema no adivina ni pregunta a la IA — hace una resta y una división, con precios reales de mercado obtenidos de Yahoo Finance:</p>
        <div class="example-box">
            <h4>Ejemplo completo: un ETF de cobre recomendado el 1 de mayo</h4>
            <table class="data-table">
                <thead>
                    <tr><th>Dato</th><th>Valor</th></tr>
                </thead>
                <tbody>
                    <tr><td>Precio del ETF el día de la recomendación (1 mayo)</td><td>42,00€</td></tr>
                    <tr><td>Precio del ETF 3 meses después (1 agosto)</td><td>46,20€</td></tr>
                    <tr><td>Precio de su benchmark el 1 mayo</td><td>100,00 (índice)</td></tr>
                    <tr><td>Precio de su benchmark el 1 agosto</td><td>103,00 (índice)</td></tr>
                </tbody>
            </table>
            <pre class="diagram-box">retorno del ETF     = (46,20 − 42,00) / 42,00 × 100  = +10,0%
retorno del benchmark = (103,00 − 100,00) / 100,00 × 100 = +3,0%

alpha (exceso sobre el benchmark) = retorno del ETF − retorno del benchmark
                                   = 10,0% − 3,0% = +7,0%</pre>
            <p>Este +10,0% de retorno y +7,0% de alpha son los dos números que se guardan para esta recomendación en concreto. El proceso se repite, exactamente igual, para las 400+ recomendaciones registradas — cada una con su propio ETF/fondo/cripto y su propio benchmark de comparación (un ETF de semiconductores se compara contra un índice de semiconductores, no contra el IBEX, para que la comparación sea justa).</p>
        </div>

        <h3>📐 Qué significan exactamente "% de aciertos" y "alpha media"</h3>
        <ul>
            <li><strong>% de aciertos (hit rate)</strong>: de todas las recomendaciones evaluadas, qué porcentaje tuvo retorno positivo (o alpha positiva, según cuál mires). Si de 197 recomendaciones 100 tuvieron retorno &gt;0%, el hit rate es 100/197 ≈ 50,8%.</li>
            <li><strong>Alpha media</strong>: la media aritmética simple del alpha de todas las recomendaciones evaluadas. Si sumas el alpha de las 197 y divides entre 197, te da ese número — puede ser negativo aunque el hit rate esté cerca del 50%, si las pérdidas cuando falla son mayores que las ganancias cuando acierta.</li>
        </ul>
        <p style="background:#f59e0b18; border-left:3px solid #f59e0b; padding:10px 14px; border-radius:6px;"><strong>Por qué miramos ambas cosas y no solo una:</strong> un motor podría acertar el 70% de las veces pero con alpha media negativa, si las pocas veces que falla lo hace estrepitosamente (fallos grandes, aciertos pequeños). O al revés: acertar poco pero con aciertos grandes que compensan. El % de aciertos solo no cuenta toda la historia — por eso el scorecard siempre muestra los dos.</p>

        <h3>🔬 La comprobación estadística: ¿es un patrón real o es casualidad?</h3>
        <p>Antes de dejar que un enfoque influya en algo, además de cumplir n≥30 y rango≥90 días, se hace una prueba estadística llamada <strong>test-t de una muestra</strong> (el mismo tipo de test que se usa en investigación científica para saber si un efecto es "real"). En términos sencillos: compara la media de los resultados (por ejemplo, +7% de alpha media) contra cero, teniendo en cuenta cuánto varían esos resultados entre sí (si todos rondan +7% es más convincente que si van de −40% a +50% con esa misma media).</p>
        <div class="formula-box">
            <p>El resultado de ese test es un <strong>p-valor</strong>: la probabilidad de que veas ese patrón "por pura casualidad" si en realidad no hubiera ningún efecto real. Usamos el umbral habitual en estadística aplicada:</p>
            <p class="formula">p-valor &lt; 0,10 → se considera "significativo" (hay indicios razonables de que no es azar)<br>
            p-valor ≥ 0,10 → no se considera concluyente, aunque ya haya pasado el filtro de n≥30 y 90 días</p>
        </div>
        <p>Es una tercera capa de seguridad, además de las dos condiciones de cantidad y de fechas: incluso si hay suficientes datos bien repartidos, si el resultado no es estadísticamente claro, se sigue mostrando pero marcado como "sin significancia estadística clara" en vez de presentarlo como una conclusión firme.</p>

        <h3>❓ Preguntas que probablemente te estés haciendo</h3>
        <div class="faq-list">
            <div class="faq-item">
                <p class="faq-q">¿Y si en 6 meses el resultado sigue siendo malo (como el 42,6% actual de aciertos frente a benchmark)?</p>
                <p>El sistema lo diría igual de claro que ahora. No hay ningún mecanismo que "maquille" un mal resultado — el scorecard es el mismo cálculo, gane o pierda el motor. Si el resultado real es que MOMENTUM no bate a su benchmark de forma consistente, la convicción de las ideas de momentum empezaría a bajar automáticamente, y tú lo verías reflejado tanto aquí como en cada oportunidad nueva.</p>
            </div>
            <div class="faq-item">
                <p class="faq-q">¿Puedo ver esto por ticker individual, no solo por enfoque?</p>
                <p>Ahora mismo el agrupamiento es por enfoque (momentum/valor) y por convicción (alta/media/baja), no por activo individual — agrupar por ticker individual necesitaría muchísimas más recomendaciones del MISMO activo exacto para tener una muestra mínima decente, algo que tardaría mucho más en darse de forma natural.</p>
            </div>
            <div class="faq-item">
                <p class="faq-q">¿Se puede "hacer trampa" metiendo 30 recomendaciones de golpe para forzar el gate?</p>
                <p>No — la condición 2 (rango de 90 días entre fechas) existe precisamente para impedir esto: 30 recomendaciones metidas el mismo día tendrían rango de fechas = 0, y se descartarían igual que el "Caso A" del ejemplo de arriba.</p>
            </div>
        </div>
    </section>

    <!-- ==================== MOTOR SISTEMÁTICO ==================== -->
    <section id="motor-sistematico">
        <h2>📈 El motor sistemático: la cartera en papel</h2>
        <p><strong>Desde cero — qué es "paper trading":</strong> significa simular una inversión con precios reales del mercado, calculando ganancias y pérdidas exactamente como si fuera dinero de verdad, pero <strong>sin mover ni un euro real</strong>. Es como practicar a conducir en un simulador antes de sacarte el carné: los reflejos que desarrollas son reales, pero si chocas no pasa nada grave. Aquí se usa para probar una estrategia de inversión "sobre el papel" durante meses, antes de decidir si algún día se usaría con dinero de verdad.</p>
        <p>Aparte de Oportunidades (que te <em>sugiere</em> ideas para que decidas tú), hay un segundo sistema completamente distinto corriendo en paralelo: una <strong>cartera con reglas fijas y automáticas</strong> — nadie, ni humano ni IA, decide semana a semana qué comprar; lo decide siempre la misma fórmula — que se reequilibra sola cada semana.</p>

        <div class="info-box" id="liveSistematicoBox">
            <strong>📡 Estado real ahora mismo</strong> <span style="font-size:11px; color:#94a3b8;">(se consulta en vivo cada vez que abres esta página — no son cifras fijas)</span>
            <p id="liveSistematicoContent" style="margin-top:8px;">Cargando datos reales del motor sistemático…</p>
        </div>

        <ul>
            <li><strong>Universo comprable</strong>: un subconjunto de ETFs/fondos ya validados como líquidos y accesibles desde los brokers reales de la cartera (nada exótico ni imposible de comprar en la vida real).</li>
            <li><strong>Tamaño de posición por volatilidad inversa</strong>: a un activo que se mueve mucho (volátil) se le asigna menos peso en la cartera; a uno más tranquilo, más peso. La idea es que cada posición aporte un riesgo parecido al total, no que todas tengan el mismo dinero encima. <em>Ejemplo: si el oro se mueve la mitad de rápido que el Bitcoin, el sistema le asigna aproximadamente el doble de peso en euros al oro que al Bitcoin, para que el "susto" potencial de cada uno sea similar.</em></li>
            <li><strong>Cinturones de seguridad</strong>: un límite máximo de peso por activo individual (para no depender demasiado de uno solo), un límite a cuánto puede pesar la cripto en total, y un "cortacircuitos" que reduce la exposición si la cartera cae demasiado desde su punto más alto.</li>
        </ul>
        <h3>El filtro antes de arriesgar dinero real: PSR</h3>
        <p><strong>Antes de nada, dos términos que hacen falta aquí:</strong></p>
        <ul>
            <li><strong>Ratio de Sharpe</strong>: mide cuánta rentabilidad obtienes por cada unidad de riesgo (de volatilidad) que asumes. Cuanto más alto, mejor "premio" te da el riesgo que corres — se explica con más detalle y ejemplos en <a href="#algoritmos">Cómo funcionan nuestros algoritmos</a>.</li>
            <li><strong>El problema con medir el Sharpe en poco tiempo</strong>: con pocos días de datos, un Sharpe alto puede ser simplemente <strong>suerte</strong> — igual que lanzar una moneda 5 veces y sacar 4 caras no demuestra que la moneda esté trucada.</li>
        </ul>
        <p>El <strong>PSR (Probabilistic Sharpe Ratio)</strong>, de Bailey &amp; López de Prado, responde a la pregunta exacta que hace falta: <em>dado lo poco (o mucho) que llevamos observando, ¿qué probabilidad hay de que ese Sharpe sea real y no un golpe de suerte?</em></p>
        <div class="example-box">
            <h4>Ejemplo: el mismo Sharpe, dos confianzas distintas</h4>
            <table class="data-table">
                <thead>
                    <tr><th>Situación</th><th>Sharpe medido</th><th>Días de datos</th><th>PSR (confianza de que sea real)</th></tr>
                </thead>
                <tbody>
                    <tr><td>Cartera A</td><td>2,4</td><td>10 días</td><td>≈ 55% — podría ser suerte</td></tr>
                    <tr><td>Cartera B</td><td>2,4</td><td>45 días</td><td>≈ 80% — ya empieza a ser creíble</td></tr>
                </tbody>
            </table>
            <p>Mismo Sharpe (2,4) en las dos, pero la confianza es muy distinta — porque B lo ha sostenido durante más tiempo. Por eso el PSR, no el Sharpe a solas, es el que decide.</p>
        </div>
        <div class="formula-box">
            <p><strong>El semáforo de salida a dinero real</strong> exige <strong>las cinco condiciones a la vez</strong> (si falta una sola, sigue en papel):</p>
            <ol style="text-align:left;">
                <li>Al menos <strong>56 días (8 semanas)</strong> y <strong>30 marcas diarias</strong> de histórico — muestra mínima, sin excepciones ni prisas.</li>
                <li>Rentabilidad por encima de su índice de referencia (el "examen" con el que se compara, p. ej. un ETF global).</li>
                <li>Sharpe por encima del de ese mismo índice de referencia.</li>
                <li><strong>PSR ≥ 75%</strong> — el resultado es estadísticamente significativo, no ruido (como en la tabla de arriba).</li>
                <li>Sin una caída (<strong>drawdown</strong>: la peor pérdida desde un máximo) catastrófica que indique que las reglas fallan en momentos duros.</li>
            </ol>
        </div>
        <p>Mientras falte cualquiera de las cinco, el propio sistema se etiqueta a sí mismo como <strong>"NO apto — sigue en papel"</strong>, con el contador exacto de días que faltan. Nadie decide a ojo cuándo "ya vale" — lo decide siempre la misma regla, y puedes ver su estado real en cualquier momento entrando a <code>fintrack-front.onrender.com/api/systematic/paper/report</code> desde el navegador.</p>

        <h3>🧮 Cómo se calcula el peso de cada activo — ejemplo con números reales</h3>
        <p>La "volatilidad inversa" no es solo una idea, es una fórmula concreta: el peso de cada activo es inversamente proporcional a su volatilidad, y luego se normaliza para que todos los pesos sumen 100%.</p>
        <div class="example-box">
            <h4>Ejemplo: repartir capital entre 3 activos</h4>
            <table class="data-table">
                <thead>
                    <tr><th>Activo</th><th>Volatilidad anual</th><th>1 / volatilidad</th><th>Peso final (normalizado)</th></tr>
                </thead>
                <tbody>
                    <tr><td>Bonos corporativos</td><td>6%</td><td>1/0,06 = 16,7</td><td>16,7 / 30,9 ≈ <strong>54%</strong></td></tr>
                    <tr><td>ETF global de acciones</td><td>15%</td><td>1/0,15 = 6,7</td><td>6,7 / 30,9 ≈ <strong>22%</strong></td></tr>
                    <tr><td>ETF de semiconductores</td><td>35%</td><td>1/0,35 = 2,9</td><td>2,9 / 30,9 ≈ <strong>9%</strong></td></tr>
                </tbody>
            </table>
            <pre class="diagram-box">Suma de "1/volatilidad" = 16,7 + 6,7 + 2,9 = 26,3 (aprox., redondeos aparte)
Peso de cada uno = su (1/volatilidad) ÷ esa suma total × 100</pre>
            <p>El activo más tranquilo (bonos) se lleva más de la mitad del capital; el más agitado (semiconductores) se lleva menos de una décima parte — así, si cualquiera de los tres tiene un mal día, el "susto" en euros es parecido entre ellos, no descompensado.</p>
        </div>
        <p>Esto se recalcula <strong>cada semana</strong> con la volatilidad más reciente de cada activo — si un activo se vuelve más tranquilo o más agitado, su peso se ajusta automáticamente la siguiente vez que se reequilibra la cartera.</p>

        <h3>📡 Qué es el "régimen de mercado" y cómo cambia las reglas</h3>
        <p>El sistema mide qué porcentaje de un universo amplio de activos cotiza por encima de su media de los últimos 200 días de mercado (una forma estándar de medir si "el mercado en general" está en tendencia alcista o bajista, ver <a href="#algoritmos">algoritmos, apartado ⑨</a>). Ahora mismo ese porcentaje ronda el <strong>78%</strong> (dato real, visible en el bloque de estado de arriba) — muy por encima del 55% que ya se considera "alcista". Cuando el régimen es claramente alcista o bajista, el sistema no cambia sus reglas de gestión de riesgo (los cinturones de seguridad siguen igual), pero sí influye en qué universo de activos considera atractivo para el reequilibrio semanal, de forma parecida a como influye en Oportunidades.</p>

        <h3>🛑 El "cortacircuitos" de drawdown, con números</h3>
        <p>El <strong>drawdown</strong> es la caída porcentual desde el punto más alto que ha alcanzado la cartera hasta el valor actual — no desde que empezaste, sino desde el mejor momento. Ahora mismo el máximo drawdown registrado en el motor sistemático es de <strong>-2,1%</strong> (dato real, ver arriba), muy lejos de activar ninguna alarma. El cortacircuitos entra en juego con caídas mucho mayores: si la cartera cayera de forma pronunciada desde su máximo, las reglas reducen automáticamente la exposición a activos de riesgo, en vez de mantener el mismo reparto pase lo que pase — es una salvaguarda contra el peor de los escenarios, no algo que se espere activar en el día a día.</p>

        <h3>🏛️ Por qué "en papel" primero — no es solo teoría</h3>
        <p>La historia de las finanzas está llena de estrategias que parecían matemáticamente impecables y acabaron mal por no haber sido puestas a prueba en condiciones reales el tiempo suficiente — el caso más citado en la industria es <strong>LTCM (Long-Term Capital Management)</strong>, un fondo de los años 90 dirigido por premios Nobel de economía, con modelos matemáticos sofisticados, que colapsó en 1998 al asumir que ciertos escenarios extremos eran "estadísticamente casi imposibles" y esos escenarios ocurrieron igualmente. La lección que se ha quedado en la gestión de riesgo moderna: <strong>ninguna fórmula, por elegante que sea, sustituye a comprobar cómo se comporta de verdad con datos y tiempo suficientes</strong> — exactamente lo que este filtro de 56 días + PSR está diseñado para forzar antes de considerar dinero real.</p>

        <h3>❓ Preguntas frecuentes</h3>
        <div class="faq-list">
            <div class="faq-item">
                <p class="faq-q">¿"Deflated Sharpe" y "PSR" son lo mismo?</p>
                <p>Están muy relacionados — el Deflated Sharpe Ratio es una versión del PSR pensada además para corregir el sesgo de haber probado <em>muchas</em> estrategias distintas antes de quedarte con la que mejor resultado dio (si pruebas 100 monedas, alguna saldrá cara 8 veces seguidas por puro azar). Aquí ambos números suelen coincidir porque solo hay una única configuración de reglas en marcha, no un proceso de prueba-y-error entre muchas variantes.</p>
            </div>
            <div class="faq-item">
                <p class="faq-q">¿Qué pasa el día que cumple las 5 condiciones?</p>
                <p>El sistema pasaría de "NO apto" a "apto" en su propio veredicto — pero eso NO significa que automáticamente se mueva dinero real. Sería el punto de partida para una decisión consciente (tuya), no una orden de compra automática.</p>
            </div>
            <div class="faq-item">
                <p class="faq-q">¿Puede este motor perder dinero real alguna vez sin que yo lo sepa?</p>
                <p>No — mientras esté "en papel" no toca ni un euro real de tu cartera. Es una simulación completa, con precios reales pero dinero ficticio, precisamente para que cualquier fallo se descubra sin coste real.</p>
            </div>
        </div>
    </section>

    <!-- ==================== QUÉ IA USAMOS ==================== -->
    <section id="que-ia-usamos">
        <h2>🤖 Qué IA usamos y por qué</h2>
        <p><strong>Desde cero — qué es un "LLM":</strong> las siglas vienen de <em>Large Language Model</em> (modelo grande de lenguaje) — es el tipo de IA detrás de ChatGPT, Gemini, Claude, etc.: un programa entrenado con muchísimo texto que predice qué palabra viene después, y con eso consigue mantener conversaciones, redactar textos o resumir información.</p>
        <p><strong>No</strong> es una IA que "piensa" en el sentido humano, ni tiene acceso a los mercados en tiempo real por sí sola — solo hace bien lo que le pidas con las palabras y los datos que le des en el mensaje.</p>
        <p>Usamos <strong>Google Gemini</strong> (capa gratuita de AI Studio) como modelo principal para todo lo que es lenguaje:</p>
        <ul>
            <li>Redactar el porqué de cada oportunidad de inversión.</li>
            <li>La nota de análisis de un activo (deep-analysis).</li>
            <li>Clasificar el sentimiento de una noticia.</li>
            <li>El chat del Asesor IA.</li>
        </ul>
        <p>Si Gemini no responde (límite de cuota agotado, error temporal), el sistema cae automáticamente a <strong>Groq</strong> como segunda opción, sin que tengas que hacer nada.</p>
        <div class="example-box">
            <h4>Ejemplo concreto: qué le pasamos a la IA y qué nos devuelve</h4>
            <p><strong>Le damos</strong>: "Este ETF tiene momentum +1,91 (top del ranking), RSI neutral, MACD alcista, retorno anualizado +721%, y esta noticia real: 'Nvidia sube precios de chips de IA un 15%'."<br>
            <strong>La IA devuelve</strong>: un párrafo en español explicando qué es el ETF, por qué esos números y esa noticia son relevantes, y los riesgos — pero <strong>usando solo esos datos</strong>, sin inventar ninguno nuevo. Si la IA fallara o no tuviera esos datos, no habría "oportunidad" que mostrar; el ranking numérico (que no depende de la IA) seguiría intacto.</p>
        </div>
        <p><strong>Por qué esta combinación y no otra</strong>: el proyecto funciona con un presupuesto de <strong>0€</strong> — cualquier modelo de pago (incluidos los más conocidos por chat, como GPT o Claude vía API) queda descartado mientras esa restricción siga en pie, por buenos que sean. Gemini y Groq tienen capas gratuitas genuinamente utilizables para este volumen de peticiones.</p>
        <p style="background:#f59e0b18; border-left:3px solid #f59e0b; padding:10px 14px; border-radius:6px;"><strong>Sobre "modelos nuevos muy fiables" que circulan por redes:</strong> si un modelo predictivo de mercados fuera realmente fiable, barato y de acceso público, dejaría de funcionar en cuanto todo el mundo lo usara — los propios mercados absorben esa ventaja (es la idea de "mercados eficientes"). La investigación académica seria sobre IA aplicada a inversión muestra mejoras modestas e inconsistentes sobre modelos de factores simples, no los resultados extraordinarios que se anuncian en Twitter o YouTube. Por eso la IA aquí tiene un rol acotado a propósito: <strong>redactar y explicar, no decidir ni predecir precio</strong> — esa decisión de diseño no depende de qué modelo de lenguaje esté de moda cada mes.</p>

        <h3>🏭 Gemini vs. Groq: no son "competidores", son cosas distintas</h3>
        <p>Es una confusión habitual, así que merece una aclaración: <strong>Gemini</strong> es un modelo de IA (creado por Google) — el "cerebro" que redacta el texto. <strong>Groq</strong> no es un modelo, es una empresa de <strong>hardware especializado</strong> (chips propios, no GPUs normales) que ejecuta modelos de otros (como Llama, de Meta) a una velocidad muy superior a la infraestructura habitual. Aquí Groq entra solo como red de seguridad: si Gemini no responde, un modelo distinto corriendo sobre la infraestructura de Groq toma el relevo para que el usuario no se quede sin respuesta.</p>

        <h3>🔒 Los tres candados técnicos que evitan que la IA "se invente cosas"</h3>
        <p>No basta con pedirle "no inventes" en el mensaje — eso ayuda pero no lo garantiza. Hay tres mecanismos técnicos reales detrás:</p>
        <ol>
            <li><strong>Esquema de salida forzado (JSON Schema)</strong>: no dejamos que la IA escriba libremente. Le exigimos una estructura fija con campos concretos (nombre, ticker, por qué ahora, riesgos, convicción...) — si intenta desviarse de esa estructura, la respuesta se rechaza automáticamente antes de llegar a la pantalla.</li>
            <li><strong>Temperatura baja</strong>: los modelos de lenguaje tienen un parámetro llamado "temperatura" que controla cuánto "improvisan" — a mayor temperatura, respuestas más creativas pero también más propensas a desviarse de los datos; a menor temperatura, respuestas más ceñidas a lo que se le ha dado. Aquí se usa una temperatura deliberadamente baja para el análisis cuantitativo, priorizando la fidelidad a los datos sobre la creatividad.</li>
            <li><strong>Verificación del ticker contra el ranking real</strong>: a la IA se le exige citar tickers que existan literalmente en la lista que el motor cuantitativo ya generó — no puede "recomendar" un activo que el motor no haya puntuado primero, así que no puede fabricar una idea de la nada.</li>
        </ol>

        <h3>📋 Para qué es buena una IA de este tipo aquí, y para qué no</h3>
        <table class="data-table">
            <thead>
                <tr><th>Buena en...</th><th>Mala en... (por eso no se le pide)</th></tr>
            </thead>
            <tbody>
                <tr><td>Redactar en lenguaje claro un dato numérico ya calculado</td><td>Calcular ella misma esos números con precisión fiable</td></tr>
                <tr><td>Resumir varias noticias y clasificar su sentimiento</td><td>Saber si el mercado subirá o bajará mañana</td></tr>
                <tr><td>Mantener una conversación con contexto de tu cartera</td><td>Recordar nada de una conversación a otra (cada consulta parte de cero, solo con lo que se le pasa esa vez)</td></tr>
                <tr><td>Adaptar el tono/idioma a quien lee</td><td>Garantizar que un hecho concreto (una fecha, una cifra) sea 100% exacto sin una fuente de datos real detrás</td></tr>
            </tbody>
        </table>
    </section>

    <!-- ==================== GLOSARIO ==================== -->
    <section id="glosario">
        <h2>📔 Glosario completo (de toda esta página, A-Z)</h2>
        <p>Todos los términos técnicos usados en <em>Cómo funcionan nuestros algoritmos</em>, <em>Autoentrenamiento</em>, <em>El motor sistemático</em> y <em>Qué IA usamos</em>, reunidos en una sola tabla para no tener que buscarlos uno a uno.</p>
        <table class="data-table">
            <thead>
                <tr><th>Término</th><th>Qué significa aquí</th></tr>
            </thead>
            <tbody>
                <tr><td><strong>Alpha</strong></td><td>El retorno de más (o de menos) que obtuvo una recomendación frente a su propio benchmark. Alpha +7% = ganó 7 puntos más que el índice con el que se compara. Ver <a href="#autoentrenamiento">Autoentrenamiento</a>.</td></tr>
                <tr><td><strong>Bollinger %B</strong></td><td>Indicador técnico que sitúa el precio dentro de su banda de volatilidad reciente (cerca del techo o del suelo). Ver <a href="#algoritmos">algoritmos ③</a>.</td></tr>
                <tr><td><strong>Convicción</strong></td><td>Etiqueta (alta/media/baja) que acompaña cada recomendación, según lo fuerte que sea su puntuación combinada.</td></tr>
                <tr><td><strong>Drawdown</strong></td><td>La peor caída porcentual desde el punto más alto alcanzado, no desde que empezaste. Mide el "dolor" máximo real.</td></tr>
                <tr><td><strong>EWMA (volatilidad)</strong></td><td>Media exponencial que da más peso a los días recientes al calcular el riesgo, para reaccionar antes que una media simple. Ver <a href="#algoritmos">algoritmos ⑤</a>.</td></tr>
                <tr><td><strong>Gate / semáforo</strong></td><td>El conjunto de condiciones numéricas que hay que cumplir TODAS a la vez antes de confiar en un resultado o pasar a dinero real. Nunca se decide "a ojo".</td></tr>
                <tr><td><strong>Hit rate</strong></td><td>% de recomendaciones evaluadas que tuvieron retorno (o alpha) positivo. Ver <a href="#autoentrenamiento">Autoentrenamiento</a>.</td></tr>
                <tr><td><strong>JSON Schema (salida forzada)</strong></td><td>Estructura fija que se le exige a la IA para responder — si se desvía, la respuesta se descarta automáticamente. Ver <a href="#que-ia-usamos">Qué IA usamos</a>.</td></tr>
                <tr><td><strong>LLM</strong></td><td><em>Large Language Model</em>: el tipo de IA (Gemini, Groq...) que redacta texto a partir de datos que se le pasan, sin "pensar" como un humano.</td></tr>
                <tr><td><strong>MACD</strong></td><td>Indicador técnico que detecta cambios de tendencia mediante el cruce de dos medias móviles. Ver <a href="#algoritmos">algoritmos ③</a>.</td></tr>
                <tr><td><strong>Momentum</strong></td><td>La fuerza de una tendencia: lo que ha subido de forma sostenida tiende a seguir subiendo a medio plazo. Ver <a href="#algoritmos">algoritmos ①</a>.</td></tr>
                <tr><td><strong>Paper trading</strong></td><td>Simular una inversión con precios reales, calculando ganancias y pérdidas reales, pero sin mover ni un euro de verdad. Ver <a href="#motor-sistematico">El motor sistemático</a>.</td></tr>
                <tr><td><strong>p-valor</strong></td><td>La probabilidad de que un resultado se deba a pura casualidad. Por debajo de 0,10 se considera un indicio razonable de que no es azar. Ver <a href="#autoentrenamiento">Autoentrenamiento</a>.</td></tr>
                <tr><td><strong>PSR (Probabilistic Sharpe Ratio)</strong></td><td>La confianza (en %) de que un Sharpe medido sea real y no un golpe de suerte, dado cuánto tiempo se ha observado. Ver <a href="#motor-sistematico">El motor sistemático</a>.</td></tr>
                <tr><td><strong>Régimen de mercado (breadth)</strong></td><td>% de un universo amplio de activos que cotiza por encima de su media de 200 sesiones — mide si el mercado en general está alcista o bajista. Ver <a href="#algoritmos">algoritmos ⑨</a>.</td></tr>
                <tr><td><strong>Reversión a la media</strong></td><td>La tendencia de un precio muy alejado de su media a "volver" hacia ella. Ver <a href="#algoritmos">algoritmos ⑥</a>.</td></tr>
                <tr><td><strong>RSI</strong></td><td>Termómetro de 0 a 100 de sobrecompra/sobreventa a corto plazo. Ver <a href="#algoritmos">algoritmos ③</a>.</td></tr>
                <tr><td><strong>Scorecard</strong></td><td>El "boletín de notas" público del motor: qué habría pasado de verdad con cada recomendación pasada. Consultable en <code>/api/scorecard</code>.</td></tr>
                <tr><td><strong>Sharpe (ratio)</strong></td><td>Retorno obtenido por cada unidad de riesgo (volatilidad) asumida. &gt;1 bueno, &gt;2 muy bueno. Ver <a href="#algoritmos">algoritmos ②</a>.</td></tr>
                <tr><td><strong>Sortino (ratio)</strong></td><td>Como el Sharpe, pero solo penaliza la volatilidad a la baja (subir a saltos no se considera "malo"). Ver <a href="#algoritmos">algoritmos ②</a>.</td></tr>
                <tr><td><strong>Temperatura (de un LLM)</strong></td><td>Parámetro que controla cuánto "improvisa" la IA — cuanto más baja, más ceñida a los datos que se le dan. Ver <a href="#que-ia-usamos">Qué IA usamos</a>.</td></tr>
                <tr><td><strong>Ticker</strong></td><td>El código corto con el que se identifica un activo en el mercado (p. ej. SOXX, BTC).</td></tr>
                <tr><td><strong>Valor / Contrarian (tesis)</strong></td><td>La segunda de las dos tesis del motor: activos castigados pero de calidad (baratos y sanos), frente al MOMENTUM.</td></tr>
                <tr><td><strong>Volatilidad anualizada</strong></td><td>Cuánto oscila el precio de un activo, expresado en términos de un año. Ver <a href="#algoritmos">algoritmos ②</a>.</td></tr>
                <tr><td><strong>Z-score (winsorizado)</strong></td><td>Cuántas desviaciones típicas se aparta un valor de la media de todo el universo comparado ese día, recortado a ±3 para evitar que un dato extremo distorsione el ranking. Ver <a href="#algoritmos">algoritmos ⑦</a>.</td></tr>
            </tbody>
        </table>
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
        <p>Por defecto es <strong>EUR</strong>. Cambiarla requiere tocar el código del backend (la moneda base del servicio de cartera, en <code>app/services/portfolio.py</code> / configuración). No es un ajuste de interfaz por ahora.</p>
        
        <h3>¿Mis datos son privados?</h3>
        <p>Es una aplicación <strong>personal y de un solo usuario</strong>, pensada solo para ti. Para funcionar como asistente en la nube, tus datos de cartera se guardan en una <strong>base de datos PostgreSQL privada</strong> (en Render), no en tu ordenador. Además se conecta a servicios externos para sus funciones: precios (Yahoo Finance, CoinGecko), noticias (RSS), el LLM que redacta los análisis (Google Gemini, con Groq de reserva) y el bot de Telegram. No se vende ni comparte tu información, pero ten en cuenta que <strong>sí viaja a esos servicios</strong> para prestar el servicio. El acceso del bot está restringido a tu chat de Telegram.</p>
        
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

            // Reflect the page in the URL so it's shareable / survives a refresh
            // (replaceState doesn't fire hashchange, so no navigation loop).
            try { history.replaceState(null, '', '#' + pageName); } catch (e) {}

            // Load dynamic content for pages
            if (pageName === 'learn') {
                loadLearnPage(targetPage);
            }
            if (pageName === 'docs') {
                targetPage.innerHTML = pageContent.docs;
                loadLiveDocsStatus();
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

    // --- Hash routing: make URLs like #opportunities or #algoritmos work ---
    window.addEventListener('hashchange', navigateFromHash);
    navigateFromHash();  // honor the hash on initial load
}

// Anchors that live inside the (dynamically injected) docs / learn pages.
const DOCS_ANCHORS = new Set(['que-es', 'guia-uso', 'el-cerebro', 'novedades', 'algoritmos',
    'autoentrenamiento', 'motor-sistematico', 'que-ia-usamos', 'glosario',
    'arquitectura', 'inicio-rapido', 'configuracion', 'añadir-posiciones', 'funcionalidades', 'api', 'faq']);
const LEARN_ANCHORS = new Set(['conceptos-basicos', 'tipos-activos', 'metricas', 'estrategias', 'riesgos', 'fiscalidad', 'corto-plazo', 'dividendos', 'divisas', 'otros-conceptos']);

function navigateFromHash() {
    const raw = decodeURIComponent((location.hash || '').replace(/^#/, '')).trim();
    if (!raw) return;

    // 0) Asset detail deep link (e.g. #asset/BTC) — not a sidebar page, so it
    // needs its own branch instead of the .nav-item lookup below.
    if (raw.startsWith('asset/') && window.showAssetDetail) {
        const ticker = raw.slice('asset/'.length);
        if (ticker) window.showAssetDetail(ticker);
        return;
    }

    // 1) Direct page name (e.g. #opportunities, #docs, #backtest)
    const navByPage = document.querySelector(`.nav-item[data-page="${raw}"]`);
    if (navByPage) {
        const pageEl = document.getElementById('page-' + raw);
        if (!pageEl || !pageEl.classList.contains('active')) navByPage.click();
        return;
    }

    // 2) Anchor inside docs/learn → open that page, then scroll to the section
    const page = DOCS_ANCHORS.has(raw) ? 'docs' : (LEARN_ANCHORS.has(raw) ? 'learn' : null);
    if (!page) return;
    const pageEl = document.getElementById('page-' + page);
    const alreadyActive = pageEl && pageEl.classList.contains('active');
    const scrollToAnchor = () => {
        const el = document.getElementById(raw);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    if (alreadyActive) {
        scrollToAnchor();
    } else {
        const nav = document.querySelector(`.nav-item[data-page="${page}"]`);
        if (nav) { nav.click(); setTimeout(scrollToAnchor, 450); }  // wait for content injection
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

