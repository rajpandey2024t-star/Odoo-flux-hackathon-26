const viewNames = {
  overview: ['Overview', 'Your subscription business at a glance.'],
  subscriptions: ['Subscriptions', 'Manage your recurring customer relationships in one place.'],
  plans: ['Plans', 'Create and manage the plans your customers can subscribe to.'],
  invoices: ['Invoices', 'Create, send and track customer invoices.'],
  customers: ['Customers', 'Keep customer details and subscription history together.'],
  team: ['Team', 'Manage staff access to your workspace.'],
  payments: ['Payments', 'Track incoming payments and outstanding balances.'],
  reports: ['Reports', 'Understand recurring revenue and subscription performance.'],
  discounts: ['Discounts', 'Create automatic discount rules for future invoices.'],
  settings: ['Settings', 'Manage your workspace preferences and team access.']
};
const overview = document.getElementById('view-overview');
const other = document.getElementById('view-other');
const breadcrumb = document.getElementById('breadcrumbCurrent');
const navLinks = [...document.querySelectorAll('[data-view]')];
const modal = document.getElementById('subscriptionModal');
const planModal = document.getElementById('planModal');
const paymentModal = document.getElementById('paymentModal');
const teamModal = document.getElementById('teamModal');
const discountModal = document.getElementById('discountModal');
let outstandingInvoices = [];

function showView(name) {
  const [title, description] = viewNames[name] || viewNames.overview;
  breadcrumb.textContent = title;
  document.title = `${title} · Subly`;
  navLinks.forEach(link => link.classList.toggle('active', link.dataset.view === name));
  const isOverview = name === 'overview';
  overview.classList.toggle('active-view', isOverview);
  other.classList.toggle('active-view', !isOverview);
  document.getElementById('otherDefault').hidden = ['plans', 'invoices', 'payments', 'team', 'discounts'].includes(name);
  document.getElementById('plansContent').hidden = name !== 'plans';
  document.getElementById('invoicesContent').hidden = name !== 'invoices';
  document.getElementById('paymentsContent').hidden = name !== 'payments';
  document.getElementById('teamContent').hidden = name !== 'team';
  document.getElementById('discountsContent').hidden = name !== 'discounts';
  if (name === 'plans') loadPlans();
  if (name === 'invoices') loadInvoices();
  if (name === 'payments') loadPayments();
  if (name === 'team') loadTeam();
  if (name === 'discounts') loadDiscounts();
  if (!isOverview && !['plans', 'invoices', 'payments', 'team', 'discounts'].includes(name)) {
    document.getElementById('otherTitle').textContent = title;
    document.getElementById('otherDescription').textContent = description;
    document.getElementById('otherEyebrow').textContent = name === 'settings' ? 'PREFERENCES' : 'WORKSPACE';
    document.getElementById('otherCreate').innerHTML = `<span class="plus">+</span> ${name === 'subscriptions' ? 'New subscription' : `Add ${title.toLowerCase().replace(/s$/, '')}`}`;
  }
  document.getElementById('sidebar').classList.remove('open');
}
navLinks.forEach(link => link.addEventListener('click', event => {
  event.preventDefault();
  showView(link.dataset.view);
  history.replaceState(null, '', `#${link.dataset.view}`);
}));

function openModal() {
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  const dateInput = modal.querySelector('[name="start"]');
  if (!dateInput.value) {
    const today = new Date();
    dateInput.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  }
  modal.querySelector('[name="customer"]').focus();
}
function closeModal() {
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
}
function openPlanModal() {
  planModal.classList.add('open');
  planModal.setAttribute('aria-hidden', 'false');
  planModal.querySelector('[name="name"]').focus();
}
function closePlanModal() {
  planModal.classList.remove('open');
  planModal.setAttribute('aria-hidden', 'true');
}
function openPaymentModal() {
  if (!outstandingInvoices.length) {
    showToast('There are no unpaid invoices. Generate an invoice first.');
    return;
  }
  const form = document.getElementById('paymentForm');
  const dateInput = form.querySelector('[name="payment_date"]');
  const today = new Date();
  dateInput.value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  syncPaymentInvoiceOptions(outstandingInvoices);
  updatePaymentAmount();
  paymentModal.classList.add('open');
  paymentModal.setAttribute('aria-hidden', 'false');
}
function closePaymentModal() {
  paymentModal.classList.remove('open');
  paymentModal.setAttribute('aria-hidden', 'true');
}
function openTeamModal() {
  teamModal.classList.add('open');
  teamModal.setAttribute('aria-hidden', 'false');
  teamModal.querySelector('[name="name"]').focus();
}
function openDiscountModal() {
  const form = document.getElementById('discountForm');
  const today = new Date();
  const dateValue = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  const end = new Date(today);
  end.setDate(end.getDate() + 30);
  const endValue = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`;
  form.querySelector('[name="start_date"]').value = dateValue;
  form.querySelector('[name="end_date"]').value = endValue;
  discountModal.classList.add('open');
  discountModal.setAttribute('aria-hidden', 'false');
  form.querySelector('[name="name"]').focus();
}
function closeDiscountModal() {
  discountModal.classList.remove('open');
  discountModal.setAttribute('aria-hidden', 'true');
}
function closeTeamModal() {
  teamModal.classList.remove('open');
  teamModal.setAttribute('aria-hidden', 'true');
}
document.getElementById('newSubscription').addEventListener('click', openModal);
document.getElementById('otherCreate').addEventListener('click', () => {
  if (breadcrumb.textContent === 'Subscriptions') openModal();
  else showToast(`${breadcrumb.textContent} setup is coming next.`);
});
document.getElementById('newPlanButton').addEventListener('click', openPlanModal);
document.getElementById('generateInvoices').addEventListener('click', generateDueInvoices);
document.getElementById('newPaymentButton').addEventListener('click', openPaymentModal);
document.getElementById('closeModal').addEventListener('click', closeModal);
document.getElementById('cancelModal').addEventListener('click', closeModal);
document.getElementById('closePlanModal').addEventListener('click', closePlanModal);
document.getElementById('cancelPlanModal').addEventListener('click', closePlanModal);
document.getElementById('closePaymentModal').addEventListener('click', closePaymentModal);
document.getElementById('cancelPaymentModal').addEventListener('click', closePaymentModal);
document.getElementById('newTeamMemberButton').addEventListener('click', openTeamModal);
document.getElementById('closeTeamModal').addEventListener('click', closeTeamModal);
document.getElementById('cancelTeamModal').addEventListener('click', closeTeamModal);
document.getElementById('newDiscountButton').addEventListener('click', openDiscountModal);
document.getElementById('closeDiscountModal').addEventListener('click', closeDiscountModal);
document.getElementById('cancelDiscountModal').addEventListener('click', closeDiscountModal);
modal.addEventListener('click', event => { if (event.target === modal) closeModal(); });
planModal.addEventListener('click', event => { if (event.target === planModal) closePlanModal(); });
paymentModal.addEventListener('click', event => { if (event.target === paymentModal) closePaymentModal(); });
teamModal.addEventListener('click', event => { if (event.target === teamModal) closeTeamModal(); });
discountModal.addEventListener('click', event => { if (event.target === discountModal) closeDiscountModal(); });
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') { closeModal(); closePlanModal(); closePaymentModal(); closeTeamModal(); closeDiscountModal(); }
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    document.getElementById('globalSearch').focus();
  }
});
function showToast(message) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 2600);
}
async function loadDashboardSummary() {
  try {
    const response = await fetch('/api/dashboard/summary');
    if (!response.ok) throw new Error('Could not load dashboard summary.');
    const summary = await response.json();
    document.getElementById('mrrValue').textContent = formatMoney(summary.monthly_recurring_revenue);
    document.getElementById('activeSubscriptionsValue').textContent = Number(summary.active_subscriptions).toLocaleString('en-IN');
    document.getElementById('customersValue').textContent = Number(summary.customers).toLocaleString('en-IN');
    document.getElementById('outstandingValue').textContent = formatMoney(summary.outstanding);
  } catch (error) {
    showToast('Could not load dashboard totals. Check that Flask is still running.');
  }
}
function formatMoney(amount) {
  return `₹${Number(amount).toLocaleString('en-IN')}`;
}
function formatDate(isoDate) {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' });
}
function syncPlanOptions(plans) {
  const select = document.querySelector('#subscriptionForm [name="plan"]');
  const previous = select.value;
  select.replaceChildren();
  plans.filter(plan => plan.active).forEach(plan => {
    const option = document.createElement('option');
    option.value = plan.name;
    option.textContent = `${plan.name} · ${formatMoney(plan.amount)} / ${plan.billing_cycle}`;
    select.append(option);
  });
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
}
function createPlanCard(plan) {
  const card = document.createElement('article');
  card.className = 'plan-card';
  card.innerHTML = '<div class="plan-card-top"><span class="plan-card-mark"></span><span class="plan-card-cycle"></span></div><h2></h2><p></p><div class="plan-card-price"><span></span><small></small></div><div class="plan-card-foot"><span>Recurring billing</span><span class="plan-card-status"><i></i>Available</span></div>';
  card.querySelector('.plan-card-mark').textContent = plan.name.slice(0, 1).toUpperCase();
  card.querySelector('.plan-card-cycle').textContent = plan.billing_cycle === 'year' ? 'YEARLY' : 'MONTHLY';
  card.querySelector('h2').textContent = plan.name;
  card.querySelector('p').textContent = plan.description || 'Subscription plan';
  card.querySelector('.plan-card-price span').textContent = formatMoney(plan.amount);
  card.querySelector('.plan-card-price small').textContent = plan.billing_cycle === 'year' ? ' / year' : ' / month';
  return card;
}
async function loadPlans() {
  try {
    const response = await fetch('/api/plans');
    if (!response.ok) throw new Error('Could not load plans.');
    const plans = await response.json();
    syncPlanOptions(plans);
    const activePlans = plans.filter(plan => plan.active);
    document.getElementById('planCount').textContent = activePlans.length;
    const grid = document.getElementById('plansGrid');
    grid.replaceChildren(...activePlans.map(createPlanCard));
    if (!activePlans.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-plans';
      empty.textContent = 'No plans yet. Create your first subscription plan to get started.';
      grid.append(empty);
    }
  } catch (error) {
    showToast('Could not load plans. Check that Flask is still running.');
  }
}
function createInvoiceRow(invoice) {
  const row = document.createElement('tr');
  row.innerHTML = '<td><span class="invoice-number"></span></td><td><div class="customer-cell"><span class="customer-avatar avatar-coral"></span><span><strong></strong><small></small></span></div></td><td><span class="plan-name"></span></td><td class="subtotal-cell"></td><td class="discount-cell"></td><td class="amount-cell"></td><td class="invoice-date"></td><td class="due-date"></td><td><span class="invoice-status"><i></i><span></span></span></td>';
  row.querySelector('.invoice-number').textContent = invoice.invoice_number;
  row.querySelector('.customer-avatar').textContent = invoice.customer.split(/\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase();
  row.querySelector('.customer-cell strong').textContent = invoice.customer;
  row.querySelector('.customer-cell small').textContent = invoice.email;
  row.querySelector('.plan-name').textContent = invoice.plan;
  row.querySelector('.subtotal-cell').textContent = formatMoney(invoice.subtotal);
  row.querySelector('.discount-cell').textContent = invoice.discount_amount ? `−${formatMoney(invoice.discount_amount)}` : '—';
  row.querySelector('.amount-cell').textContent = formatMoney(invoice.amount);
  row.querySelector('.invoice-date').textContent = formatDate(invoice.invoice_date);
  row.querySelector('.due-date').textContent = formatDate(invoice.due_date);
  const status = row.querySelector('.invoice-status');
  status.querySelector('span').textContent = invoice.status;
  if (invoice.due_date < new Date().toISOString().slice(0, 10) && invoice.status !== 'Paid') status.classList.add('overdue');
  return row;
}
async function loadInvoices() {
  try {
    const response = await fetch('/api/invoices');
    if (!response.ok) throw new Error('Could not load invoices.');
    const invoices = await response.json();
    outstandingInvoices = invoices.filter(invoice => invoice.balance_due > 0);
    syncPaymentInvoiceOptions(outstandingInvoices);
    document.getElementById('invoiceCount').textContent = invoices.length;
    document.getElementById('invoiceRows').replaceChildren(...invoices.map(createInvoiceRow));
    document.getElementById('invoiceEmpty').hidden = invoices.length > 0;
  } catch (error) {
    showToast('Could not load invoices. Check that Flask is still running.');
  }
}
function syncPaymentInvoiceOptions(invoices) {
  const select = document.querySelector('#paymentForm [name="invoice_id"]');
  if (!select) return;
  const previous = select.value;
  select.replaceChildren();
  invoices.forEach(invoice => {
    const option = document.createElement('option');
    option.value = invoice.id;
    option.dataset.balance = invoice.balance_due;
    option.textContent = `${invoice.invoice_number} · ${invoice.customer} · ${formatMoney(invoice.balance_due)} due`;
    select.append(option);
  });
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
}
function updatePaymentAmount() {
  const select = document.querySelector('#paymentForm [name="invoice_id"]');
  const selected = select.selectedOptions[0];
  document.querySelector('#paymentForm [name="amount"]').value = selected ? selected.dataset.balance : '';
}
function createPaymentRow(payment) {
  const row = document.createElement('tr');
  row.innerHTML = '<td><span class="plan-name"></span></td><td><span class="invoice-number"></span></td><td><div class="customer-cell"><span class="customer-avatar avatar-green"></span><span><strong></strong></span></div></td><td><span class="plan-name"></span></td><td class="amount-cell"></td><td class="payment-date"></td><td class="payment-note"></td>';
  row.querySelector('td:first-child .plan-name').textContent = `PAY-${String(payment.id).padStart(5, '0')}`;
  row.querySelector('.invoice-number').textContent = payment.invoice_number;
  row.querySelector('.customer-avatar').textContent = payment.customer.split(/\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase();
  row.querySelector('.customer-cell strong').textContent = payment.customer;
  row.querySelector('td:nth-child(4) .plan-name').textContent = payment.method;
  row.querySelector('.amount-cell').textContent = formatMoney(payment.amount);
  row.querySelector('.payment-date').textContent = formatDate(payment.payment_date);
  row.querySelector('.payment-note').textContent = payment.note || '—';
  return row;
}
async function loadPayments() {
  try {
    await loadInvoices();
    const response = await fetch('/api/payments');
    if (!response.ok) throw new Error('Could not load payments.');
    const payments = await response.json();
    document.getElementById('paymentCount').textContent = payments.length;
    document.getElementById('paymentRows').replaceChildren(...payments.map(createPaymentRow));
    document.getElementById('paymentEmpty').hidden = payments.length > 0;
  } catch (error) {
    showToast('Could not load payments. Check that Flask is still running.');
  }
}
function createTeamRow(member) {
  const row = document.createElement('tr');
  row.innerHTML = '<td><div class="customer-cell"><span class="customer-avatar avatar-blue"></span><span><strong></strong></span></div></td><td class="team-email"></td><td><span class="team-role"><i></i>Staff</span></td>';
  row.querySelector('.customer-avatar').textContent = member.name.split(/\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase();
  row.querySelector('.customer-cell strong').textContent = member.name;
  row.querySelector('.team-email').textContent = member.email;
  return row;
}
async function loadTeam() {
  try {
    const response = await fetch('/api/team');
    const members = await response.json();
    if (!response.ok) throw new Error(members.error || 'Could not load team members.');
    document.getElementById('teamRows').replaceChildren(...members.map(createTeamRow));
    document.getElementById('teamEmpty').hidden = members.length > 0;
  } catch (error) {
    showToast(error.message || 'Could not load team members.');
  }
}
function createDiscountRow(rule) {
  const row = document.createElement('tr');
  row.innerHTML = '<td><span class="discount-rule-name"></span></td><td><span class="discount-value"></span></td><td class="discount-minimum"></td><td><span class="discount-dates"></span></td><td class="discount-uses"></td><td><span class="discount-state"></span></td>';
  row.querySelector('.discount-rule-name').textContent = rule.name;
  row.querySelector('.discount-value').textContent = rule.discount_type === 'percentage' ? `${rule.value}%` : formatMoney(rule.value);
  row.querySelector('.discount-minimum').textContent = rule.minimum_amount ? formatMoney(rule.minimum_amount) : 'No minimum';
  row.querySelector('.discount-dates').textContent = `${formatDate(rule.start_date)} – ${formatDate(rule.end_date)}`;
  row.querySelector('.discount-uses').textContent = rule.usage_limit ? `${rule.used_count} / ${rule.usage_limit}` : `${rule.used_count} / Unlimited`;
  const state = row.querySelector('.discount-state');
  const today = new Date().toISOString().slice(0, 10);
  if (rule.end_date < today) state.textContent = 'Expired';
  else if (rule.start_date > today) state.textContent = 'Scheduled';
  else if (rule.usage_limit && rule.used_count >= rule.usage_limit) state.textContent = 'Limit reached';
  else state.textContent = 'Active';
  state.className = `discount-rule-state ${state.textContent === 'Active' ? 'active' : ''}`;
  return row;
}
async function loadDiscounts() {
  try {
    const response = await fetch('/api/discounts');
    const rules = await response.json();
    if (!response.ok) throw new Error(rules.error || 'Could not load discount rules.');
    document.getElementById('discountRows').replaceChildren(...rules.map(createDiscountRow));
    document.getElementById('discountEmpty').hidden = rules.length > 0;
  } catch (error) {
    showToast(error.message || 'Could not load discount rules.');
  }
}
async function generateDueInvoices() {
  const button = document.getElementById('generateInvoices');
  button.disabled = true;
  try {
    const response = await fetch('/api/invoices/generate-due', { method: 'POST' });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Invoices could not be generated.');
    await loadInvoices();
    showToast(result.created ? `${result.created} due invoice${result.created === 1 ? '' : 's'} generated.` : 'No new subscriptions are due for billing.');
  } catch (error) {
    showToast(error.message || 'Could not generate invoices.');
  } finally {
    button.disabled = false;
  }
}
function createSubscriptionRow(subscription, index = 0) {
  const row = document.createElement('tr');
  row.dataset.status = subscription.status;
  row.innerHTML = '<td><input type="checkbox" aria-label="Select customer"></td><td><div class="customer-cell"><span class="customer-avatar"></span><span><strong></strong><small></small></span></div></td><td><span class="plan-name"></span><small class="plan-cycle"></small></td><td class="amount-cell"><span class="amount-value"></span><span class="cycle-value"></span></td><td class="billing-date"></td><td><span class="status-pill"><i></i><span class="status-text"></span></span></td><td><button class="row-more" aria-label="More actions">···</button></td>';
  const initials = subscription.customer.split(/\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase();
  const avatarColors = ['avatar-coral', 'avatar-blue', 'avatar-purple', 'avatar-green', 'avatar-yellow'];
  row.querySelector('.customer-avatar').textContent = initials;
  row.querySelector('.customer-avatar').classList.add(avatarColors[index % avatarColors.length]);
  row.querySelector('.customer-cell strong').textContent = subscription.customer;
  row.querySelector('.customer-cell small').textContent = subscription.email;
  row.querySelector('.plan-name').textContent = subscription.plan;
  row.querySelector('.plan-cycle').textContent = subscription.billing_cycle === 'year' ? 'Annual plan' : 'Monthly plan';
  row.querySelector('.amount-value').textContent = formatMoney(subscription.amount);
  row.querySelector('.cycle-value').textContent = subscription.billing_cycle === 'year' ? ' / year' : ' / month';
  row.querySelector('.billing-date').textContent = formatDate(subscription.next_billing);
  const statusClass = subscription.status === 'Past due' ? 'status-past' : subscription.status === 'Trial' ? 'status-trial' : 'status-active';
  row.querySelector('.status-pill').classList.add(statusClass);
  row.querySelector('.status-text').textContent = subscription.status;
  return row;
}
function filterRows() {
  const query = document.getElementById('tableSearch').value.trim().toLowerCase();
  const selected = document.querySelector('.table-tab.selected')?.dataset.filter || 'all';
  let shown = 0;
  document.querySelectorAll('#subscriptionRows tr').forEach(row => {
    const matchesQuery = row.innerText.toLowerCase().includes(query);
    const matchesStatus = selected === 'all' || row.dataset.status === selected;
    row.hidden = !(matchesQuery && matchesStatus);
    if (!row.hidden) shown++;
  });
  document.getElementById('rowCount').textContent = shown;
}
function renderSubscriptions(subscriptions) {
  const body = document.getElementById('subscriptionRows');
  body.replaceChildren(...subscriptions.map((subscription, index) => createSubscriptionRow(subscription, index)));
  document.getElementById('rowCount').textContent = subscriptions.length;
  filterRows();
}
async function loadSubscriptions() {
  try {
    const response = await fetch('/api/subscriptions');
    if (!response.ok) throw new Error('Could not load subscriptions.');
    renderSubscriptions(await response.json());
  } catch (error) {
    showToast('Could not connect to the app. Check that Flask is still running.');
  }
}
document.querySelectorAll('.table-tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.table-tab').forEach(item => item.classList.remove('selected'));
  tab.classList.add('selected');
  filterRows();
}));
document.getElementById('tableSearch').addEventListener('input', filterRows);
document.querySelector('#paymentForm [name="invoice_id"]').addEventListener('change', updatePaymentAmount);
document.getElementById('globalSearch').addEventListener('input', event => {
  if (event.target.value) {
    showView('subscriptions');
    document.getElementById('tableSearch').value = event.target.value;
    filterRows();
  }
});
document.getElementById('filterButton').addEventListener('click', () => showToast('Use the status tabs to filter subscriptions.'));
document.getElementById('periodSelect').addEventListener('click', () => showToast('Revenue chart is showing the last 12 months.'));
document.getElementById('exportButton').addEventListener('click', () => showToast('Report export will be available in a later step.'));
document.querySelectorAll('.pagination button:not(:disabled)').forEach(button => button.addEventListener('click', () => showToast('Pagination will be connected after we add more records.')));

document.getElementById('subscriptionForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const submitButton = form.querySelector('[type="submit"]');
  submitButton.disabled = true;
  try {
    const response = await fetch('/api/subscriptions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer: values.get('customer'), email: values.get('email'), plan: values.get('plan'), start: values.get('start') })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Subscription could not be saved.');
    closeModal();
    form.reset();
    document.querySelector('.table-tab[data-filter="all"]').click();
    showView('overview');
    await loadSubscriptions();
    showToast('Subscription saved to the database.');
  } catch (error) {
    showToast(error.message || 'Could not save subscription. Check that Flask is running.');
  } finally {
    submitButton.disabled = false;
  }
});

document.getElementById('planForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const submitButton = form.querySelector('[type="submit"]');
  submitButton.disabled = true;
  try {
    const response = await fetch('/api/plans', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: values.get('name'), amount: values.get('amount'), billing_cycle: values.get('billing_cycle'), description: values.get('description') })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Plan could not be saved.');
    form.reset();
    closePlanModal();
    await loadPlans();
    showToast('Plan saved to the database.');
  } catch (error) {
    showToast(error.message || 'Could not save plan. Check that Flask is running.');
  } finally {
    submitButton.disabled = false;
  }
});

document.getElementById('paymentForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const submitButton = form.querySelector('[type="submit"]');
  submitButton.disabled = true;
  try {
    const response = await fetch('/api/payments', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        invoice_id: values.get('invoice_id'),
        amount: values.get('amount'),
        method: values.get('method'),
        payment_date: values.get('payment_date'),
        note: values.get('note')
      })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Payment could not be saved.');
    form.reset();
    closePaymentModal();
    await loadPayments();
    showToast('Payment saved. Invoice balance has been updated.');
  } catch (error) {
    showToast(error.message || 'Could not save payment. Check that Flask is running.');
  } finally {
    submitButton.disabled = false;
  }
});

document.getElementById('teamForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const submitButton = form.querySelector('[type="submit"]');
  submitButton.disabled = true;
  try {
    const response = await fetch('/api/team', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: values.get('name'), email: values.get('email'), password: values.get('password') })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Staff account could not be created.');
    form.reset();
    closeTeamModal();
    await loadTeam();
    showToast('Staff account created.');
  } catch (error) {
    showToast(error.message || 'Could not create staff account.');
  } finally {
    submitButton.disabled = false;
  }
});

document.getElementById('discountForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const submitButton = form.querySelector('[type="submit"]');
  submitButton.disabled = true;
  try {
    const response = await fetch('/api/discounts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: values.get('name'),
        discount_type: values.get('discount_type'),
        value: values.get('value'),
        minimum_amount: values.get('minimum_amount'),
        usage_limit: values.get('usage_limit'),
        start_date: values.get('start_date'),
        end_date: values.get('end_date')
      })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Discount rule could not be saved.');
    form.reset();
    closeDiscountModal();
    await loadDiscounts();
    showToast('Discount rule saved. It can apply to future invoices.');
  } catch (error) {
    showToast(error.message || 'Could not save discount rule.');
  } finally {
    submitButton.disabled = false;
  }
});

document.getElementById('menuToggle').addEventListener('click', () => document.getElementById('sidebar').classList.toggle('open'));
document.addEventListener('click', event => {
  const sidebar = document.getElementById('sidebar');
  if (window.innerWidth <= 820 && sidebar.classList.contains('open') && !sidebar.contains(event.target) && !event.target.closest('#menuToggle')) sidebar.classList.remove('open');
});
const today = new Date();
document.getElementById('todayDate').textContent = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).format(today).toUpperCase();
loadPlans();
loadSubscriptions();
loadDashboardSummary();
