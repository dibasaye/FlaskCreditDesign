import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Client, Product, Credit, CreditPayment, SavingsAccount, SavingsTransaction, PaymentSchedule, AuditLog, ClientInteraction, SystemSettings, Notification, CreditDocument
from forms import LoginForm, ClientForm, ProductForm, CreditForm, CreditPaymentForm, SavingsAccountForm, SavingsTransactionForm, ProfileForm, ChangePasswordForm, LoanSimulationForm, ClientInteractionForm, SystemSettingsForm, UserForm
from sqlalchemy import func
import random
import string
from dateutil.relativedelta import relativedelta

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET") or "dev-secret-key-change-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_unique_id(prefix, model, field):
    while True:
        random_part = ''.join(random.choices(string.digits, k=8))
        unique_id = f"{prefix}{random_part}"
        if not model.query.filter(getattr(model, field) == unique_id).first():
            return unique_id

def log_audit(action, entity_type=None, entity_id=None, details=None):
    log = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=request.remote_addr
    )
    db.session.add(log)

def generate_payment_schedule(credit):
    if not credit.disbursement_date:
        return
    
    PaymentSchedule.query.filter_by(credit_id=credit.id).delete()
    
    start_date = credit.disbursement_date
    for i in range(1, credit.duration_months + 1):
        due_date = start_date + relativedelta(months=i)
        schedule = PaymentSchedule(
            credit_id=credit.id,
            installment_number=i,
            due_date=due_date.date(),
            expected_amount=credit.monthly_payment
        )
        db.session.add(schedule)

def calculate_penalties(credit):
    from datetime import datetime, timedelta
    penalty_rate = 0.05
    total_penalty = 0
    
    for installment in credit.payment_schedule:
        if not installment.paid and installment.due_date < datetime.now().date():
            days_late = (datetime.now().date() - installment.due_date).days
            if days_late > 0:
                penalty = installment.expected_amount * penalty_rate * (days_late / 30)
                total_penalty += penalty
    
    return round(total_penalty, 2)

def calculate_client_credit_score(client):
    total_credits = Credit.query.filter_by(client_id=client.id).count()
    if total_credits == 0:
        return 50
    
    completed_credits = Credit.query.filter_by(client_id=client.id, status='completed').count()
    active_credits = Credit.query.filter_by(client_id=client.id, status='active').all()
    
    score = 50
    
    if total_credits > 0:
        completion_rate = completed_credits / total_credits
        score += completion_rate * 30
    
    for credit in active_credits:
        if credit.amount_paid > 0:
            payment_ratio = credit.amount_paid / credit.total_amount
            score += payment_ratio * 10
        
        overdue_count = len(credit.overdue_installments)
        if overdue_count > 0:
            score -= overdue_count * 5
    
    return max(0, min(100, round(score, 2)))

def apply_savings_interest(account):
    if account.status != 'active':
        return
    
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    last_transaction = SavingsTransaction.query.filter_by(
        account_id=account.id,
        transaction_type='interest'
    ).order_by(SavingsTransaction.transaction_date.desc()).first()
    
    current_date = datetime.now()
    last_interest_date = last_transaction.transaction_date if last_transaction else account.opening_date
    
    delta = relativedelta(current_date, last_interest_date)
    months_passed = delta.years * 12 + delta.months
    
    if months_passed >= 1 and account.balance > 0:
        monthly_rate = account.interest_rate / 100 / 12
        interest_amount = account.balance * monthly_rate * months_passed
        
        account.balance += interest_amount
        
        transaction = SavingsTransaction(
            account_id=account.id,
            transaction_type='interest',
            amount=interest_amount,
            balance_after=account.balance,
            notes=f'Intérêts calculés pour {months_passed} mois'
        )
        db.session.add(transaction)

def generate_payment_alerts():
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    alert_window = today + timedelta(days=7)
    
    upcoming_payments = PaymentSchedule.query.filter(
        PaymentSchedule.due_date <= alert_window,
        PaymentSchedule.due_date >= today,
        PaymentSchedule.paid == False
    ).all()
    
    for payment in upcoming_payments:
        credit = payment.credit
        days_until_due = (payment.due_date - today).days
        
        existing_alert = Notification.query.filter_by(
            notification_type='payment_reminder',
            related_entity_type='PaymentSchedule',
            related_entity_id=payment.id,
            is_read=False
        ).first()
        
        if not existing_alert:
            all_admins = User.query.filter(User.role.in_(['administrateur', 'gestionnaire'])).all()
            
            for admin in all_admins:
                notification = Notification(
                    user_id=admin.id,
                    title=f'Échéance dans {days_until_due} jour(s)',
                    message=f'Le crédit {credit.credit_number} de {credit.client.full_name} a une échéance de {payment.expected_amount} FCFA le {payment.due_date.strftime("%d/%m/%Y")}',
                    notification_type='payment_reminder',
                    related_entity_type='PaymentSchedule',
                    related_entity_id=payment.id
                )
                db.session.add(notification)
    
    overdue_payments = PaymentSchedule.query.filter(
        PaymentSchedule.due_date < today,
        PaymentSchedule.paid == False
    ).all()
    
    for payment in overdue_payments:
        credit = payment.credit
        days_overdue = (today - payment.due_date).days
        
        existing_alert = Notification.query.filter_by(
            notification_type='payment_overdue',
            related_entity_type='PaymentSchedule',
            related_entity_id=payment.id,
            is_read=False
        ).first()
        
        if not existing_alert:
            all_admins = User.query.filter(User.role.in_(['administrateur', 'gestionnaire'])).all()
            
            for admin in all_admins:
                notification = Notification(
                    user_id=admin.id,
                    title=f'⚠️ Paiement en retard de {days_overdue} jour(s)',
                    message=f'ALERTE: Le crédit {credit.credit_number} de {credit.client.full_name} a un paiement en retard depuis le {payment.due_date.strftime("%d/%m/%Y")}. Montant: {payment.expected_amount} FCFA',
                    notification_type='payment_overdue',
                    related_entity_type='PaymentSchedule',
                    related_entity_id=payment.id
                )
                db.session.add(notification)
    
    db.session.commit()

with app.app_context():
    db.create_all()
    
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    
    if admin_username and admin_password and not User.query.filter_by(username=admin_username).first():
        admin = User(username=admin_username, email=admin_email, role='administrateur')
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Utilisateur administrateur '{admin_username}' créé avec succès")
    
    default_users = [
        {'username': 'gestionnaire1', 'email': 'gestionnaire1@finance.com', 'password': 'Manager@123', 'role': 'gestionnaire'},
        {'username': 'gestionnaire2', 'email': 'gestionnaire2@finance.com', 'password': 'Manager@123', 'role': 'gestionnaire'},
        {'username': 'agent1', 'email': 'agent1@finance.com', 'password': 'Agent@123', 'role': 'agent'},
        {'username': 'agent2', 'email': 'agent2@finance.com', 'password': 'Agent@123', 'role': 'agent'},
        {'username': 'agent3', 'email': 'agent3@finance.com', 'password': 'Agent@123', 'role': 'agent'},
    ]
    
    for user_data in default_users:
        if not User.query.filter_by(username=user_data['username']).first():
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                role=user_data['role']
            )
            user.set_password(user_data['password'])
            db.session.add(user)
    
    db.session.commit()
    
    if not SystemSettings.query.first():
        default_settings = SystemSettings()
        db.session.add(default_settings)
        db.session.commit()
        print("Paramètres système par défaut créés")

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Connexion réussie!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnexion réussie', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    generate_payment_alerts()
    
    from datetime import datetime, timedelta
    from sqlalchemy import extract
    
    total_clients = Client.query.count()
    total_credits = Credit.query.count()
    active_credits = Credit.query.filter_by(status='active').count()
    total_savings = SavingsAccount.query.count()
    
    total_credit_amount = db.session.query(func.sum(Credit.amount)).filter(Credit.status.in_(['active', 'approved', 'disbursed'])).scalar() or 0
    total_credit_paid = db.session.query(func.sum(Credit.amount_paid)).filter(Credit.status.in_(['active', 'approved', 'disbursed'])).scalar() or 0
    total_savings_balance = db.session.query(func.sum(SavingsAccount.balance)).filter_by(status='active').scalar() or 0
    
    recent_credits = Credit.query.order_by(Credit.application_date.desc()).limit(5).all()
    recent_clients = Client.query.order_by(Client.created_at.desc()).limit(5).all()
    
    pending_credits = Credit.query.filter_by(status='pending').count()
    approved_credits = Credit.query.filter_by(status='approved').count()
    completed_credits = Credit.query.filter_by(status='completed').count()
    rejected_credits = Credit.query.filter_by(status='rejected').count()
    
    credit_products = Product.query.filter_by(product_type='credit', active=True).count()
    savings_products = Product.query.filter_by(product_type='savings', active=True).count()
    
    upcoming_due = PaymentSchedule.query.filter(
        PaymentSchedule.due_date <= datetime.now().date() + timedelta(days=7),
        PaymentSchedule.due_date >= datetime.now().date(),
        PaymentSchedule.paid == False
    ).count()
    
    overdue = PaymentSchedule.query.filter(
        PaymentSchedule.due_date < datetime.now().date(),
        PaymentSchedule.paid == False
    ).count()
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    new_clients_month = Client.query.filter(Client.created_at >= thirty_days_ago).count()
    new_credits_month = Credit.query.filter(Credit.application_date >= thirty_days_ago).count()
    
    monthly_data = []
    monthly_labels = []
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=30*i)
        month_name = month_date.strftime('%B')
        month_num = month_date.month
        year = month_date.year
        
        credits_count = Credit.query.filter(
            extract('month', Credit.application_date) == month_num,
            extract('year', Credit.application_date) == year
        ).count()
        
        credits_amount = db.session.query(func.sum(Credit.amount)).filter(
            extract('month', Credit.application_date) == month_num,
            extract('year', Credit.application_date) == year
        ).scalar() or 0
        
        payments_amount = db.session.query(func.sum(CreditPayment.amount)).join(Credit).filter(
            extract('month', CreditPayment.payment_date) == month_num,
            extract('year', CreditPayment.payment_date) == year
        ).scalar() or 0
        
        monthly_labels.append(month_name[:3])
        monthly_data.append({
            'credits_count': credits_count,
            'credits_amount': float(credits_amount),
            'payments_amount': float(payments_amount)
        })
    
    total_payments = db.session.query(func.sum(CreditPayment.amount)).scalar() or 0
    avg_credit_amount = db.session.query(func.avg(Credit.amount)).filter(Credit.status.in_(['active', 'approved', 'disbursed'])).scalar() or 0
    avg_savings_balance = db.session.query(func.avg(SavingsAccount.balance)).filter_by(status='active').scalar() or 0
    
    repayment_rate = (total_credit_paid / total_credit_amount * 100) if total_credit_amount > 0 else 0
    
    risk_clients = Credit.query.filter(
        Credit.status == 'active',
        Credit.penalty_amount > 0
    ).count()
    
    return render_template('dashboard.html',
                         total_clients=total_clients,
                         total_credits=total_credits,
                         active_credits=active_credits,
                         total_savings=total_savings,
                         total_credit_amount=total_credit_amount,
                         total_credit_paid=total_credit_paid,
                         total_savings_balance=total_savings_balance,
                         recent_credits=recent_credits,
                         recent_clients=recent_clients,
                         pending_credits=pending_credits,
                         approved_credits=approved_credits,
                         completed_credits=completed_credits,
                         rejected_credits=rejected_credits,
                         credit_products=credit_products,
                         savings_products=savings_products,
                         upcoming_due=upcoming_due,
                         overdue=overdue,
                         new_clients_month=new_clients_month,
                         new_credits_month=new_credits_month,
                         monthly_labels=monthly_labels,
                         monthly_data=monthly_data,
                         total_payments=total_payments,
                         avg_credit_amount=avg_credit_amount,
                         avg_savings_balance=avg_savings_balance,
                         repayment_rate=repayment_rate,
                         risk_clients=risk_clients)

@app.route('/clients')
@login_required
def clients():
    search_query = request.args.get('search', '')
    filter_status = request.args.get('status', '')
    
    query = Client.query
    
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                Client.first_name.ilike(search_pattern),
                Client.last_name.ilike(search_pattern),
                Client.client_id.ilike(search_pattern),
                Client.email.ilike(search_pattern),
                Client.phone.ilike(search_pattern)
            )
        )
    
    clients_list = query.order_by(Client.created_at.desc()).all()
    return render_template('clients.html', clients=clients_list, search_query=search_query)

@app.route('/clients/new', methods=['GET', 'POST'])
@login_required
def new_client():
    form = ClientForm()
    if form.validate_on_submit():
        client = Client(
            client_id=generate_unique_id('CLT', Client, 'client_id'),
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            date_of_birth=form.date_of_birth.data,
            id_number=form.id_number.data
        )
        db.session.add(client)
        db.session.commit()
        flash(f'Client {client.full_name} créé avec succès!', 'success')
        return redirect(url_for('clients'))
    return render_template('client_form.html', form=form, title='Nouveau Client')

@app.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(id):
    client = Client.query.get_or_404(id)
    form = ClientForm(obj=client)
    if form.validate_on_submit():
        form.populate_obj(client)
        client.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Client {client.full_name} mis à jour avec succès!', 'success')
        return redirect(url_for('client_detail', id=id))
    return render_template('client_form.html', form=form, title='Modifier Client', client=client)

@app.route('/clients/<int:id>')
@login_required
def client_detail(id):
    client = Client.query.get_or_404(id)
    interaction_form = ClientInteractionForm()
    credit_score = calculate_client_credit_score(client)
    return render_template('client_detail.html', client=client, interaction_form=interaction_form, credit_score=credit_score)

@app.route('/clients/<int:id>/interaction', methods=['POST'])
@login_required
def add_client_interaction(id):
    client = Client.query.get_or_404(id)
    form = ClientInteractionForm()
    
    if form.validate_on_submit():
        interaction = ClientInteraction(
            client_id=id,
            user_id=current_user.id,
            interaction_type=form.interaction_type.data,
            subject=form.subject.data,
            notes=form.notes.data
        )
        db.session.add(interaction)
        log_audit('Interaction client ajoutée', 'ClientInteraction', None, f'Interaction avec {client.full_name}: {form.subject.data}')
        db.session.commit()
        flash('Interaction enregistrée avec succès!', 'success')
    
    return redirect(url_for('client_detail', id=id))

@app.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def delete_client(id):
    if current_user.role != 'administrateur':
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('clients'))
    
    client = Client.query.get_or_404(id)
    db.session.delete(client)
    db.session.commit()
    flash(f'Client {client.full_name} supprimé avec succès!', 'success')
    return redirect(url_for('clients'))

@app.route('/products')
@login_required
def products():
    products_list = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('products.html', products=products_list)

@app.route('/products/new', methods=['GET', 'POST'])
@login_required
def new_product():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            product_type=form.product_type.data,
            interest_rate=form.interest_rate.data,
            min_amount=form.min_amount.data,
            max_amount=form.max_amount.data,
            min_duration=form.min_duration.data,
            max_duration=form.max_duration.data,
            description=form.description.data,
            active=form.active.data
        )
        db.session.add(product)
        db.session.commit()
        flash(f'Produit {product.name} créé avec succès!', 'success')
        return redirect(url_for('products'))
    return render_template('product_form.html', form=form, title='Nouveau Produit')

@app.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        form.populate_obj(product)
        db.session.commit()
        flash(f'Produit {product.name} mis à jour avec succès!', 'success')
        return redirect(url_for('products'))
    return render_template('product_form.html', form=form, title='Modifier Produit', product=product)

@app.route('/credits')
@login_required
def credits():
    search_query = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = Credit.query.join(Client)
    
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                Credit.credit_number.ilike(search_pattern),
                Client.first_name.ilike(search_pattern),
                Client.last_name.ilike(search_pattern),
                Client.client_id.ilike(search_pattern)
            )
        )
    
    if status_filter:
        query = query.filter(Credit.status == status_filter)
    
    credits_list = query.order_by(Credit.application_date.desc()).all()
    return render_template('credits.html', credits=credits_list, search_query=search_query, status_filter=status_filter)

@app.route('/credits/new', methods=['GET', 'POST'])
@login_required
def new_credit():
    form = CreditForm()
    form.client_id.choices = [(c.id, c.full_name) for c in Client.query.order_by(Client.last_name).all()]
    form.product_id.choices = [(p.id, p.name) for p in Product.query.filter_by(product_type='credit', active=True).all()]
    
    if form.validate_on_submit():
        client = Client.query.get(form.client_id.data)
        credit_score = calculate_client_credit_score(client)
        
        product = Product.query.get(form.product_id.data)
        amount = form.amount.data
        duration = form.duration_months.data
        rate = product.interest_rate / 100 / 12
        
        if rate > 0:
            monthly_payment = (amount * rate * (1 + rate)**duration) / ((1 + rate)**duration - 1)
        else:
            monthly_payment = amount / duration
        
        total_amount = monthly_payment * duration
        
        credit = Credit(
            credit_number=generate_unique_id('CRD', Credit, 'credit_number'),
            client_id=form.client_id.data,
            product_id=form.product_id.data,
            amount=amount,
            interest_rate=product.interest_rate,
            duration_months=duration,
            monthly_payment=round(monthly_payment, 2),
            total_amount=round(total_amount, 2),
            notes=form.notes.data,
            credit_score=credit_score,
            status='pending'
        )
        db.session.add(credit)
        log_audit('Demande de crédit créée', 'Credit', None, f'Demande de crédit pour {client.full_name}')
        db.session.commit()
        flash(f'Demande de crédit {credit.credit_number} créée avec succès! Score de solvabilité: {credit_score}/100', 'success')
        return redirect(url_for('credits'))
    
    return render_template('credit_form.html', form=form, title='Nouvelle Demande de Crédit')

@app.route('/credits/<int:id>')
@login_required
def credit_detail(id):
    credit = Credit.query.get_or_404(id)
    payment_form = CreditPaymentForm()
    
    if credit.status == 'active':
        penalty = calculate_penalties(credit)
        if penalty != credit.penalty_amount:
            credit.penalty_amount = penalty
            db.session.commit()
    
    return render_template('credit_detail.html', credit=credit, payment_form=payment_form)

@app.route('/credits/<int:id>/approve', methods=['POST'])
@login_required
def approve_credit(id):
    if current_user.role not in ['administrateur', 'gestionnaire']:
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('credits'))
    
    credit = Credit.query.get_or_404(id)
    credit.status = 'approved'
    credit.approval_date = datetime.utcnow()
    db.session.commit()
    flash(f'Crédit {credit.credit_number} approuvé avec succès!', 'success')
    return redirect(url_for('credit_detail', id=id))

@app.route('/credits/<int:id>/disburse', methods=['POST'])
@login_required
def disburse_credit(id):
    if current_user.role not in ['administrateur', 'gestionnaire']:
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('credits'))
    
    credit = Credit.query.get_or_404(id)
    if credit.status == 'approved':
        credit.status = 'active'
        credit.disbursement_date = datetime.utcnow()
        generate_payment_schedule(credit)
        log_audit('Crédit décaissé', 'Credit', credit.id, f'Crédit {credit.credit_number} décaissé')
        db.session.commit()
        flash(f'Crédit {credit.credit_number} décaissé avec succès!', 'success')
    return redirect(url_for('credit_detail', id=id))

@app.route('/credits/<int:id>/payment', methods=['POST'])
@login_required
def add_credit_payment(id):
    credit = Credit.query.get_or_404(id)
    form = CreditPaymentForm()
    
    if form.validate_on_submit():
        payment = CreditPayment(
            credit_id=id,
            amount=form.amount.data,
            payment_method=form.payment_method.data,
            reference=form.reference.data,
            notes=form.notes.data
        )
        credit.amount_paid += form.amount.data
        
        if credit.amount_paid >= credit.total_amount:
            credit.status = 'completed'
        
        db.session.add(payment)
        db.session.commit()
        flash(f'Paiement de {form.amount.data} enregistré avec succès!', 'success')
    
    return redirect(url_for('credit_detail', id=id))

@app.route('/loan-simulation', methods=['GET', 'POST'])
@login_required
def loan_simulation():
    form = LoanSimulationForm()
    form.product_id.choices = [(p.id, p.name) for p in Product.query.filter_by(product_type='credit', active=True).all()]
    
    simulation_result = None
    if form.validate_on_submit():
        product = Product.query.get(form.product_id.data)
        amount = form.amount.data
        duration = form.duration_months.data
        rate = product.interest_rate / 100 / 12
        
        if rate > 0:
            monthly_payment = (amount * rate * (1 + rate)**duration) / ((1 + rate)**duration - 1)
        else:
            monthly_payment = amount / duration
        
        total_amount = monthly_payment * duration
        total_interest = total_amount - amount
        
        simulation_result = {
            'product_name': product.name,
            'amount': amount,
            'duration': duration,
            'interest_rate': product.interest_rate,
            'monthly_payment': round(monthly_payment, 2),
            'total_amount': round(total_amount, 2),
            'total_interest': round(total_interest, 2)
        }
    
    return render_template('loan_simulation.html', form=form, simulation=simulation_result)

@app.route('/savings')
@login_required
def savings():
    savings_list = SavingsAccount.query.order_by(SavingsAccount.opening_date.desc()).all()
    return render_template('savings.html', savings=savings_list)

@app.route('/savings/new', methods=['GET', 'POST'])
@login_required
def new_savings():
    form = SavingsAccountForm()
    form.client_id.choices = [(c.id, c.full_name) for c in Client.query.order_by(Client.last_name).all()]
    form.product_id.choices = [(p.id, p.name) for p in Product.query.filter_by(product_type='savings', active=True).all()]
    
    if form.validate_on_submit():
        product = Product.query.get(form.product_id.data)
        account = SavingsAccount(
            account_number=generate_unique_id('SAV', SavingsAccount, 'account_number'),
            client_id=form.client_id.data,
            product_id=form.product_id.data,
            interest_rate=product.interest_rate,
            balance=form.initial_deposit.data or 0
        )
        db.session.add(account)
        
        if form.initial_deposit.data and form.initial_deposit.data > 0:
            transaction = SavingsTransaction(
                account_id=account.id,
                transaction_type='deposit',
                amount=form.initial_deposit.data,
                balance_after=form.initial_deposit.data,
                notes='Dépôt initial'
            )
            db.session.add(transaction)
        
        db.session.commit()
        flash(f'Compte d\'épargne {account.account_number} créé avec succès!', 'success')
        return redirect(url_for('savings'))
    
    return render_template('savings_form.html', form=form, title='Nouveau Compte d\'Épargne')

@app.route('/savings/<int:id>')
@login_required
def savings_detail(id):
    account = SavingsAccount.query.get_or_404(id)
    transaction_form = SavingsTransactionForm()
    return render_template('savings_detail.html', account=account, transaction_form=transaction_form)

@app.route('/savings/<int:id>/close', methods=['POST'])
@login_required
def close_savings_account(id):
    if current_user.role not in ['administrateur', 'gestionnaire']:
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('savings'))
    
    account = SavingsAccount.query.get_or_404(id)
    
    if account.balance > 0:
        flash('Impossible de clôturer un compte avec un solde positif. Effectuez un retrait complet d\'abord.', 'danger')
        return redirect(url_for('savings_detail', id=id))
    
    account.status = 'closed'
    account.closing_date = datetime.utcnow()
    log_audit('Compte d\'épargne clôturé', 'SavingsAccount', account.id, f'Compte {account.account_number} clôturé')
    db.session.commit()
    flash(f'Compte d\'épargne {account.account_number} clôturé avec succès!', 'success')
    return redirect(url_for('savings'))

@app.route('/savings/<int:id>/apply-interest', methods=['POST'])
@login_required
def apply_interest(id):
    if current_user.role not in ['administrateur', 'gestionnaire']:
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('savings'))
    
    account = SavingsAccount.query.get_or_404(id)
    apply_savings_interest(account)
    log_audit('Intérêts d\'épargne appliqués', 'SavingsAccount', account.id, f'Intérêts calculés pour le compte {account.account_number}')
    db.session.commit()
    flash(f'Intérêts appliqués au compte {account.account_number}!', 'success')
    return redirect(url_for('savings_detail', id=id))

@app.route('/savings/<int:id>/transaction', methods=['POST'])
@login_required
def add_savings_transaction(id):
    account = SavingsAccount.query.get_or_404(id)
    form = SavingsTransactionForm()
    
    if form.validate_on_submit():
        amount = form.amount.data
        transaction_type = form.transaction_type.data
        
        if transaction_type == 'withdrawal' and amount > account.balance:
            flash('Solde insuffisant pour ce retrait', 'danger')
            return redirect(url_for('savings_detail', id=id))
        
        if transaction_type == 'deposit':
            account.balance += amount
        else:
            account.balance -= amount
        
        transaction = SavingsTransaction(
            account_id=id,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=account.balance,
            reference=form.reference.data,
            notes=form.notes.data
        )
        db.session.add(transaction)
        db.session.commit()
        flash(f'Transaction de {amount} enregistrée avec succès!', 'success')
    
    return redirect(url_for('savings_detail', id=id))

@app.route('/analytics')
@login_required
def analytics():
    from datetime import datetime, timedelta
    from sqlalchemy import extract
    
    today = datetime.now().date()
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    total_clients = Client.query.count()
    total_credits = Credit.query.count()
    active_credits = Credit.query.filter_by(status='active').count()
    
    total_disbursed = db.session.query(func.sum(Credit.amount)).filter(
        Credit.status.in_(['active', 'approved', 'disbursed', 'completed'])
    ).scalar() or 0
    
    total_recovered = db.session.query(func.sum(Credit.amount_paid)).filter(
        Credit.status.in_(['active', 'completed'])
    ).scalar() or 0
    
    total_outstanding = total_disbursed - total_recovered
    recovery_rate = (total_recovered / total_disbursed * 100) if total_disbursed > 0 else 0
    
    credits_by_month = []
    payments_by_month = []
    month_labels = []
    
    for i in range(11, -1, -1):
        month_date = datetime.now() - timedelta(days=30*i)
        month_name = month_date.strftime('%b %Y')
        month_num = month_date.month
        year = month_date.year
        
        month_credits = db.session.query(func.sum(Credit.amount)).filter(
            extract('month', Credit.application_date) == month_num,
            extract('year', Credit.application_date) == year
        ).scalar() or 0
        
        month_payments = db.session.query(func.sum(CreditPayment.amount)).join(Credit).filter(
            extract('month', CreditPayment.payment_date) == month_num,
            extract('year', CreditPayment.payment_date) == year
        ).scalar() or 0
        
        month_labels.append(month_name)
        credits_by_month.append(float(month_credits))
        payments_by_month.append(float(month_payments))
    
    avg_last_3_months = sum(credits_by_month[-3:]) / 3 if len(credits_by_month) >= 3 else 0
    projected_next_month = avg_last_3_months
    
    clients_by_status = {
        'active': Client.query.join(Credit).filter(Credit.status == 'active').distinct().count(),
        'completed': Client.query.join(Credit).filter(Credit.status == 'completed').distinct().count(),
        'no_credit': Client.query.outerjoin(Credit).group_by(Client.id).having(func.count(Credit.id) == 0).count()
    }
    
    top_clients = db.session.query(
        Client,
        func.count(Credit.id).label('credit_count'),
        func.sum(Credit.amount).label('total_amount')
    ).join(Credit).group_by(Client.id).order_by(func.sum(Credit.amount).desc()).limit(10).all()
    
    overdue_credits = Credit.query.join(PaymentSchedule).filter(
        Credit.status == 'active',
        PaymentSchedule.paid == False,
        PaymentSchedule.due_date < today
    ).distinct().count()
    
    total_penalties = db.session.query(func.sum(Credit.penalty_amount)).filter(
        Credit.status == 'active'
    ).scalar() or 0
    
    portfolio_quality = {
        'excellent': Credit.query.filter(Credit.status == 'active', Credit.credit_score >= 80).count(),
        'good': Credit.query.filter(Credit.status == 'active', Credit.credit_score >= 60, Credit.credit_score < 80).count(),
        'medium': Credit.query.filter(Credit.status == 'active', Credit.credit_score >= 40, Credit.credit_score < 60).count(),
        'poor': Credit.query.filter(Credit.status == 'active', Credit.credit_score < 40).count()
    }
    
    products_performance = db.session.query(
        Product.name,
        func.count(Credit.id).label('count'),
        func.sum(Credit.amount).label('total_amount'),
        func.avg(Credit.credit_score).label('avg_score')
    ).join(Credit).group_by(Product.id, Product.name).all()
    
    return render_template('analytics.html',
                         total_clients=total_clients,
                         total_credits=total_credits,
                         active_credits=active_credits,
                         total_disbursed=total_disbursed,
                         total_recovered=total_recovered,
                         total_outstanding=total_outstanding,
                         recovery_rate=recovery_rate,
                         month_labels=month_labels,
                         credits_by_month=credits_by_month,
                         payments_by_month=payments_by_month,
                         projected_next_month=projected_next_month,
                         clients_by_status=clients_by_status,
                         top_clients=top_clients,
                         overdue_credits=overdue_credits,
                         total_penalties=total_penalties,
                         portfolio_quality=portfolio_quality,
                         products_performance=products_performance)

@app.route('/map')
@login_required
def client_map():
    clients = Client.query.all()
    
    clients_data = []
    import random
    base_lat = 5.3600
    base_lng = -4.0083
    
    for client in clients:
        lat_offset = random.uniform(-0.5, 0.5)
        lng_offset = random.uniform(-0.5, 0.5)
        
        active_credits = Credit.query.filter_by(client_id=client.id, status='active').count()
        total_amount = db.session.query(func.sum(Credit.amount)).filter_by(client_id=client.id).scalar() or 0
        
        status_color = 'green' if active_credits == 0 else 'blue' if active_credits == 1 else 'orange'
        
        clients_data.append({
            'id': client.id,
            'name': client.full_name,
            'client_id': client.client_id,
            'address': client.address or 'Adresse non renseignée',
            'phone': client.phone or 'N/A',
            'email': client.email or 'N/A',
            'lat': base_lat + lat_offset,
            'lng': base_lng + lng_offset,
            'active_credits': active_credits,
            'total_amount': float(total_amount),
            'color': status_color
        })
    
    return render_template('map.html', clients_data=clients_data)

@app.route('/reports')
@login_required
def reports():
    total_clients = Client.query.count()
    total_active_credits = Credit.query.filter_by(status='active').count()
    total_completed_credits = Credit.query.filter_by(status='completed').count()
    total_pending_credits = Credit.query.filter_by(status='pending').count()
    
    total_credit_disbursed = db.session.query(func.sum(Credit.amount)).filter(
        Credit.status.in_(['active', 'completed'])
    ).scalar() or 0
    
    total_credit_recovered = db.session.query(func.sum(Credit.amount_paid)).filter(
        Credit.status.in_(['active', 'completed'])
    ).scalar() or 0
    
    total_penalties = db.session.query(func.sum(Credit.penalty_amount)).filter(
        Credit.status == 'active'
    ).scalar() or 0
    
    recovery_rate = (total_credit_recovered / total_credit_disbursed * 100) if total_credit_disbursed > 0 else 0
    
    total_savings_accounts = SavingsAccount.query.filter_by(status='active').count()
    total_savings_balance = db.session.query(func.sum(SavingsAccount.balance)).filter_by(status='active').scalar() or 0
    
    credits_at_risk = Credit.query.filter_by(status='active').all()
    at_risk_count = sum(1 for c in credits_at_risk if len(c.overdue_installments) > 0)
    
    recent_audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()
    
    monthly_stats = db.session.query(
        func.date_trunc('month', Credit.application_date).label('month'),
        func.count(Credit.id).label('count'),
        func.sum(Credit.amount).label('total')
    ).filter(
        Credit.application_date >= datetime.utcnow() - relativedelta(months=12)
    ).group_by('month').order_by('month').all()
    
    return render_template('reports.html',
                         total_clients=total_clients,
                         total_active_credits=total_active_credits,
                         total_completed_credits=total_completed_credits,
                         total_pending_credits=total_pending_credits,
                         total_credit_disbursed=total_credit_disbursed,
                         total_credit_recovered=total_credit_recovered,
                         total_penalties=total_penalties,
                         recovery_rate=recovery_rate,
                         total_savings_accounts=total_savings_accounts,
                         total_savings_balance=total_savings_balance,
                         at_risk_count=at_risk_count,
                         recent_audits=recent_audits,
                         monthly_stats=monthly_stats)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    profile_form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()
    
    system_settings = SystemSettings.query.first()
    if not system_settings:
        system_settings = SystemSettings()
        db.session.add(system_settings)
        db.session.commit()
    
    settings_form = SystemSettingsForm(obj=system_settings)
    
    if profile_form.validate_on_submit() and 'profile_submit' in request.form:
        existing_user = User.query.filter(User.username == profile_form.username.data, User.id != current_user.id).first()
        if existing_user:
            flash('Ce nom d\'utilisateur est déjà utilisé', 'danger')
        else:
            current_user.username = profile_form.username.data
            current_user.email = profile_form.email.data
            db.session.commit()
            flash('Profil mis à jour avec succès!', 'success')
            return redirect(url_for('settings'))
    
    if password_form.validate_on_submit() and 'password_submit' in request.form:
        if not current_user.check_password(password_form.current_password.data):
            flash('Mot de passe actuel incorrect', 'danger')
        elif password_form.new_password.data != password_form.confirm_password.data:
            flash('Les nouveaux mots de passe ne correspondent pas', 'danger')
        else:
            current_user.set_password(password_form.new_password.data)
            db.session.commit()
            flash('Mot de passe changé avec succès!', 'success')
            return redirect(url_for('settings'))
    
    if settings_form.validate_on_submit() and 'system_submit' in request.form:
        if current_user.role != 'administrateur':
            flash('Accès non autorisé', 'danger')
            return redirect(url_for('settings'))
        
        settings_form.populate_obj(system_settings)
        db.session.commit()
        flash('Paramètres système mis à jour avec succès!', 'success')
        return redirect(url_for('settings'))
    
    users = User.query.all() if current_user.role == 'administrateur' else []
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    
    return render_template('settings.html', 
                         profile_form=profile_form, 
                         password_form=password_form,
                         settings_form=settings_form,
                         users=users,
                         unread_notifications=unread_notifications)

@app.route('/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    if current_user.role != 'administrateur':
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('settings'))
    
    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Ce nom d\'utilisateur existe déjà', 'danger')
        elif User.query.filter_by(email=form.email.data).first():
            flash('Cet email est déjà utilisé', 'danger')
        else:
            user = User(username=form.username.data, email=form.email.data, role=form.role.data)
            user.set_password(form.password.data or 'ChangeMe123')
            db.session.add(user)
            log_audit('Utilisateur créé', 'User', None, f'Utilisateur {user.username} créé')
            db.session.commit()
            flash(f'Utilisateur {user.username} créé avec succès!', 'success')
            return redirect(url_for('settings'))
    return render_template('user_form.html', form=form, title='Nouvel Utilisateur')

@app.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != 'administrateur':
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('settings'))
    
    user = User.query.get_or_404(id)
    form = UserForm(obj=user)
    
    if form.validate_on_submit():
        existing = User.query.filter(User.username == form.username.data, User.id != id).first()
        if existing:
            flash('Ce nom d\'utilisateur est déjà utilisé', 'danger')
        else:
            user.username = form.username.data
            user.email = form.email.data
            user.role = form.role.data
            if form.password.data:
                user.set_password(form.password.data)
            log_audit('Utilisateur modifié', 'User', user.id, f'Utilisateur {user.username} modifié')
            db.session.commit()
            flash(f'Utilisateur {user.username} mis à jour avec succès!', 'success')
            return redirect(url_for('settings'))
    
    return render_template('user_form.html', form=form, title='Modifier Utilisateur', user=user)

@app.route('/users/<int:id>/delete', methods=['POST'])
@login_required
def delete_user(id):
    if current_user.role != 'administrateur':
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('settings'))
    
    if id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte', 'danger')
        return redirect(url_for('settings'))
    
    user = User.query.get_or_404(id)
    username = user.username
    db.session.delete(user)
    log_audit('Utilisateur supprimé', 'User', id, f'Utilisateur {username} supprimé')
    db.session.commit()
    flash(f'Utilisateur {username} supprimé avec succès!', 'success')
    return redirect(url_for('settings'))

@app.route('/export/clients')
@login_required
def export_clients():
    import csv
    from io import StringIO
    from flask import make_response
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID Client', 'Prénom', 'Nom', 'Email', 'Téléphone', 'Date de naissance', 'Date de création'])
    
    clients = Client.query.all()
    for client in clients:
        writer.writerow([
            client.client_id,
            client.first_name,
            client.last_name,
            client.email or '',
            client.phone or '',
            client.date_of_birth.strftime('%Y-%m-%d') if client.date_of_birth else '',
            client.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=clients_export.csv'
    response.headers['Content-Type'] = 'text/csv'
    log_audit('Export clients', 'Client', None, f'{len(clients)} clients exportés')
    return response

@app.route('/export/credits')
@login_required
def export_credits():
    import csv
    from io import StringIO
    from flask import make_response
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Numéro', 'Client', 'Produit', 'Montant', 'Taux', 'Durée', 'Paiement Mensuel', 'Montant Total', 'Montant Payé', 'Solde', 'Statut', 'Date Demande'])
    
    credits = Credit.query.all()
    for credit in credits:
        writer.writerow([
            credit.credit_number,
            credit.client.full_name,
            credit.product.name,
            credit.amount,
            credit.interest_rate,
            credit.duration_months,
            credit.monthly_payment,
            credit.total_amount,
            credit.amount_paid,
            credit.balance,
            credit.status,
            credit.application_date.strftime('%Y-%m-%d')
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=credits_export.csv'
    response.headers['Content-Type'] = 'text/csv'
    log_audit('Export crédits', 'Credit', None, f'{len(credits)} crédits exportés')
    return response

@app.route('/export/savings')
@login_required
def export_savings():
    import csv
    from io import StringIO
    from flask import make_response
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Numéro Compte', 'Client', 'Produit', 'Solde', 'Taux d\'intérêt', 'Statut', 'Date Ouverture'])
    
    accounts = SavingsAccount.query.all()
    for account in accounts:
        writer.writerow([
            account.account_number,
            account.client.full_name,
            account.product.name,
            account.balance,
            account.interest_rate,
            account.status,
            account.opening_date.strftime('%Y-%m-%d')
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=savings_export.csv'
    response.headers['Content-Type'] = 'text/csv'
    log_audit('Export épargne', 'SavingsAccount', None, f'{len(accounts)} comptes exportés')
    return response

@app.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_notification_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id != current_user.id:
        flash('Accès non autorisé', 'danger')
        return redirect(url_for('notifications'))
    
    notification.is_read = True
    db.session.commit()
    return redirect(url_for('notifications'))

@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('Toutes les notifications ont été marquées comme lues', 'success')
    return redirect(url_for('notifications'))

@app.route('/clients/<int:id>/credit-history')
@login_required
def client_credit_history(id):
    client = Client.query.get_or_404(id)
    credits = Credit.query.filter_by(client_id=id).order_by(Credit.application_date.desc()).all()
    
    total_borrowed = sum(c.amount for c in credits if c.status in ['active', 'completed'])
    total_repaid = sum(c.amount_paid for c in credits)
    current_debt = sum(c.balance for c in credits if c.status == 'active')
    
    completed_on_time = sum(1 for c in credits if c.status == 'completed' and len(c.overdue_installments) == 0)
    total_completed = sum(1 for c in credits if c.status == 'completed')
    
    on_time_rate = (completed_on_time / total_completed * 100) if total_completed > 0 else 100
    credit_score = calculate_client_credit_score(client)
    
    return render_template('client_credit_history.html', 
                         client=client,
                         credits=credits,
                         total_borrowed=total_borrowed,
                         total_repaid=total_repaid,
                         current_debt=current_debt,
                         on_time_rate=on_time_rate,
                         credit_score=credit_score)

@app.template_filter('currency')
def currency_filter(value):
    if value is None:
        value = 0
    return f"{value:,.2f} FCFA"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
