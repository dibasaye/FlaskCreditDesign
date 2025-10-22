from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SelectField, FloatField, IntegerField, TextAreaField, DateField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange

class LoginForm(FlaskForm):
    username = StringField('Nom d\'utilisateur', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Mot de passe', validators=[DataRequired()])

class ClientForm(FlaskForm):
    first_name = StringField('Prénom', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Nom', validators=[DataRequired(), Length(max=100)])
    email = EmailField('Email', validators=[Optional(), Email()])
    phone = StringField('Téléphone', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Adresse', validators=[Optional()])
    date_of_birth = DateField('Date de naissance', validators=[Optional()], format='%Y-%m-%d')
    id_number = StringField('Numéro d\'identité', validators=[Optional(), Length(max=50)])

class ProductForm(FlaskForm):
    name = StringField('Nom du produit', validators=[DataRequired(), Length(max=100)])
    product_type = SelectField('Type de produit', choices=[('credit', 'Crédit'), ('savings', 'Épargne')], validators=[DataRequired()])
    interest_rate = FloatField('Taux d\'intérêt (%)', validators=[DataRequired(), NumberRange(min=0, max=100)])
    min_amount = FloatField('Montant minimum', validators=[Optional(), NumberRange(min=0)])
    max_amount = FloatField('Montant maximum', validators=[Optional(), NumberRange(min=0)])
    min_duration = IntegerField('Durée minimum (mois)', validators=[Optional(), NumberRange(min=1)])
    max_duration = IntegerField('Durée maximum (mois)', validators=[Optional(), NumberRange(min=1)])
    description = TextAreaField('Description', validators=[Optional()])
    active = BooleanField('Actif')

class CreditForm(FlaskForm):
    client_id = SelectField('Client', coerce=int, validators=[DataRequired()])
    product_id = SelectField('Produit de crédit', coerce=int, validators=[DataRequired()])
    amount = FloatField('Montant demandé', validators=[DataRequired(), NumberRange(min=1)])
    duration_months = IntegerField('Durée (mois)', validators=[DataRequired(), NumberRange(min=1)])
    notes = TextAreaField('Notes', validators=[Optional()])

class CreditPaymentForm(FlaskForm):
    amount = FloatField('Montant du paiement', validators=[DataRequired(), NumberRange(min=0.01)])
    payment_method = StringField('Méthode de paiement', validators=[Optional(), Length(max=50)])
    reference = StringField('Référence', validators=[Optional(), Length(max=100)])
    notes = TextAreaField('Notes', validators=[Optional()])

class SavingsAccountForm(FlaskForm):
    client_id = SelectField('Client', coerce=int, validators=[DataRequired()])
    product_id = SelectField('Produit d\'épargne', coerce=int, validators=[DataRequired()])
    initial_deposit = FloatField('Dépôt initial', validators=[Optional(), NumberRange(min=0)])

class SavingsTransactionForm(FlaskForm):
    transaction_type = SelectField('Type de transaction', choices=[('deposit', 'Dépôt'), ('withdrawal', 'Retrait')], validators=[DataRequired()])
    amount = FloatField('Montant', validators=[DataRequired(), NumberRange(min=0.01)])
    reference = StringField('Référence', validators=[Optional(), Length(max=100)])
    notes = TextAreaField('Notes', validators=[Optional()])
