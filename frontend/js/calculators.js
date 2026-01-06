/**
 * Financial Calculators
 * Compound interest, FIRE, DCA, and Dividend calculators
 */

// Format currency helper
function formatCalcCurrency(value) {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: 'EUR',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(value);
}

/**
 * Compound Interest Calculator
 * Formula: FV = P(1 + r/n)^(nt) + PMT × (((1 + r/n)^(nt) - 1) / (r/n))
 */
function calculateCompound() {
    const initial = parseFloat(document.getElementById('ci_initial').value) || 0;
    const monthly = parseFloat(document.getElementById('ci_monthly').value) || 0;
    const rate = parseFloat(document.getElementById('ci_rate').value) / 100 || 0;
    const years = parseInt(document.getElementById('ci_years').value) || 0;
    
    const monthlyRate = rate / 12;
    const months = years * 12;
    
    // Calculate future value with compound interest and monthly contributions
    let futureValue = initial;
    for (let i = 0; i < months; i++) {
        futureValue = futureValue * (1 + monthlyRate) + monthly;
    }
    
    const totalContributed = initial + (monthly * months);
    const totalInterest = futureValue - totalContributed;
    
    // Update UI
    document.querySelector('#compoundResult .result-value').textContent = formatCalcCurrency(futureValue);
    document.getElementById('ci_contributed').textContent = formatCalcCurrency(totalContributed);
    document.getElementById('ci_interest').textContent = formatCalcCurrency(totalInterest);
    
    // Highlight result
    highlightResult('compoundResult');
}

/**
 * FIRE Calculator (Financial Independence, Retire Early)
 * Uses the 4% rule (or custom SWR) to calculate the FIRE number
 */
function calculateFIRE() {
    const annualExpenses = parseFloat(document.getElementById('fire_expenses').value) || 0;
    const swr = parseFloat(document.getElementById('fire_swr').value) / 100 || 0.04;
    const currentPortfolio = parseFloat(document.getElementById('fire_current').value) || 0;
    const monthlySavings = parseFloat(document.getElementById('fire_savings').value) || 0;
    
    // FIRE number = Annual Expenses / Safe Withdrawal Rate
    const fireNumber = annualExpenses / swr;
    
    // Calculate progress
    const progress = (currentPortfolio / fireNumber) * 100;
    
    // Calculate years to FIRE (assuming 7% annual return)
    const annualReturn = 0.07;
    const annualSavings = monthlySavings * 12;
    
    let yearsToFire = 0;
    let portfolio = currentPortfolio;
    
    while (portfolio < fireNumber && yearsToFire < 100) {
        portfolio = portfolio * (1 + annualReturn) + annualSavings;
        yearsToFire++;
    }
    
    // Update UI
    document.querySelector('#fireResult .result-value').textContent = formatCalcCurrency(fireNumber);
    document.getElementById('fire_years').textContent = yearsToFire < 100 ? `${yearsToFire} años` : 'N/A';
    document.getElementById('fire_progress').textContent = `${progress.toFixed(1)}%`;
    
    highlightResult('fireResult');
}

/**
 * DCA (Dollar Cost Averaging) Calculator
 * Simulates regular periodic investments
 */
function calculateDCA() {
    const monthlyAmount = parseFloat(document.getElementById('dca_amount').value) || 0;
    const months = parseInt(document.getElementById('dca_months').value) || 0;
    const annualReturn = parseFloat(document.getElementById('dca_return').value) / 100 || 0;
    
    const monthlyReturn = annualReturn / 12;
    
    // Calculate future value with DCA
    let futureValue = 0;
    for (let i = 0; i < months; i++) {
        futureValue = (futureValue + monthlyAmount) * (1 + monthlyReturn);
    }
    
    const totalInvested = monthlyAmount * months;
    const totalGain = futureValue - totalInvested;
    
    // Update UI
    document.querySelector('#dcaResult .result-value').textContent = formatCalcCurrency(futureValue);
    document.getElementById('dca_invested').textContent = formatCalcCurrency(totalInvested);
    document.getElementById('dca_gain').textContent = formatCalcCurrency(totalGain);
    
    highlightResult('dcaResult');
}

/**
 * Dividend Income Calculator
 * Calculates projected dividend income with dividend growth
 */
function calculateDividends() {
    const capital = parseFloat(document.getElementById('div_capital').value) || 0;
    const yieldRate = parseFloat(document.getElementById('div_yield').value) / 100 || 0;
    const growthRate = parseFloat(document.getElementById('div_growth').value) / 100 || 0;
    const years = parseInt(document.getElementById('div_years').value) || 0;
    
    // Calculate dividends with growth
    let annualDividend = capital * yieldRate;
    let totalDividends = 0;
    
    for (let i = 0; i < years; i++) {
        totalDividends += annualDividend;
        annualDividend *= (1 + growthRate);
    }
    
    const monthlyDividend = annualDividend / 12;
    
    // Update UI
    document.querySelector('#divResult .result-value').textContent = formatCalcCurrency(annualDividend);
    document.getElementById('div_monthly').textContent = formatCalcCurrency(monthlyDividend);
    document.getElementById('div_total').textContent = formatCalcCurrency(totalDividends);
    
    highlightResult('divResult');
}

/**
 * Highlight the result box briefly
 */
function highlightResult(elementId) {
    const element = document.getElementById(elementId);
    element.style.borderColor = 'var(--accent-primary)';
    element.style.boxShadow = '0 0 20px rgba(0, 212, 170, 0.2)';
    
    setTimeout(() => {
        element.style.borderColor = '';
        element.style.boxShadow = '';
    }, 1500);
}

// Initialize calculators with default calculations on page load
document.addEventListener('DOMContentLoaded', () => {
    // Run initial calculations
    setTimeout(() => {
        if (document.getElementById('ci_initial')) calculateCompound();
        if (document.getElementById('fire_expenses')) calculateFIRE();
        if (document.getElementById('dca_amount')) calculateDCA();
        if (document.getElementById('div_capital')) calculateDividends();
    }, 500);
});

