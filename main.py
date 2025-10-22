import os
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Client, Product, Credit, CreditPayment, SavingsAccount, SavingsTransaction
from forms import LoginForm, ClientForm, ProductForm, CreditForm, CreditPaymentForm, SavingsAccountForm, SavingsTransactionForm
from sqlalchemy import func
import random
import string

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
    
    credit_products = Product.query.filter_by(product_type='credit', active=True).count()
    savings_products = Product.query.filter_by(product_type='savings', active=True).count()
    
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
                         credit_products=credit_products,
                         savings_products=savings_products)

@app.route('/clients')
@login_required
def clients():
    clients_list = Client.query.order_by(Client.created_at.desc()).all()
    return render_template('clients.html', clients=clients_list)

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
    return render_template('client_detail.html', client=client)

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
    credits_list = Credit.query.order_by(Credit.application_date.desc()).all()
    return render_template('credits.html', credits=credits_list)

@app.route('/credits/new', methods=['GET', 'POST'])
@login_required
def new_credit():
    form = CreditForm()
    form.client_id.choices = [(c.id, c.full_name) for c in Client.query.order_by(Client.last_name).all()]
    form.product_id.choices = [(p.id, p.name) for p in Product.query.filter_by(product_type='credit', active=True).all()]
    
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
            status='pending'
        )
        db.session.add(credit)
        db.session.commit()
        flash(f'Demande de crédit {credit.credit_number} créée avec succès!', 'success')
        return redirect(url_for('credits'))
    
    return render_template('credit_form.html', form=form, title='Nouvelle Demande de Crédit')

@app.route('/credits/<int:id>')
@login_required
def credit_detail(id):
    credit = Credit.query.get_or_404(id)
    payment_form = CreditPaymentForm()
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

@app.template_filter('currency')
def currency_filter(value):
    if value is None:
        value = 0
    return f"{value:,.2f} FCFA"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
