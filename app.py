from flask import Flask, render_template, session, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, FloatField
from wtforms.validators import DataRequired, Length, NumberRange
import csv
import io
import click

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # Change this to a strong, random key in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

class ProductForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(min=2, max=100)])
    price = FloatField('Цена', validators=[DataRequired(), NumberRange(min=0)])
    description = TextAreaField('Описание', validators=[Length(max=1024)])
    image_file = StringField('Файл изображения (например, image.jpg)', validators=[DataRequired(), Length(max=20)])
    brand = StringField('Бренд', validators=[Length(max=50)])
    submit = SubmitField('Добавить товар')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    brand = db.Column(db.String(50), nullable=True) # New column

    def __repr__(self):
        return f"Product('{self.name}', '{self.price}')"

@app.route("/")
@app.route("/home")
def home():
    products_query = Product.query

    # Filtering logic
    search_query = request.args.get('search', '').strip()
    selected_brand = request.args.get('brand', '').strip()
    
    if search_query:
        products_query = products_query.filter(Product.name.ilike(f'%{search_query}%'))
    
    if selected_brand:
        products_query = products_query.filter_by(brand=selected_brand)

    products = products_query.all()

    all_brands = sorted(list(set(p.brand for p in Product.query.all() if p.brand)))

    return render_template('home.html', products=products, search_query=search_query, selected_brand=selected_brand, all_brands=all_brands)

@app.route("/product/<int:product_id>")
def product(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    if 'cart' not in session:
        session['cart'] = []
    
    found = False
    for item in session['cart']:
        if item['id'] == product.id:
            item['quantity'] += 1
            found = True
            break
    if not found:
        session['cart'].append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'image_file': product.image_file,
            'quantity': 1
        })
    session.modified = True
    flash(f'{product.name} добавлен в корзину!', 'success')
    return redirect(request.referrer or url_for('home'))

@app.route("/cart")
def cart():
    cart_items = session.get('cart', [])
    total_price = sum(item['price'] * item['quantity'] for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route("/clear_cart")
def clear_cart():
    session['cart'] = []
    session.modified = True
    flash('Корзина очищена!', 'info')
    return redirect(url_for('cart'))

@app.route("/admin_login", methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'password': # Hardcoded for demo
            session['logged_in'] = True
            flash('Вы успешно вошли как администратор!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Неверный логин или пароль.', 'danger')
    return render_template('admin_login.html')

@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get('logged_in'):
        flash('Пожалуйста, войдите, чтобы получить доступ к этой странице.', 'danger')
        return redirect(url_for('admin_login'))
    products = Product.query.all()
    return render_template('admin_dashboard.html', products=products)

@app.route("/admin/add_product", methods=['GET', 'POST'])
def add_product():
    if not session.get('logged_in'):
        flash('Пожалуйста, войдите, чтобы получить доступ к этой странице.', 'danger')
        return redirect(url_for('admin_login'))
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(name=form.name.data,
                          price=form.price.data,
                          description=form.description.data,
                          image_file=form.image_file.data,
                          brand=form.brand.data)
        db.session.add(product)
        db.session.commit()
        flash('Товар был успешно добавлен!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_product.html', title='Добавить товар', form=form)

@app.route("/admin/bulk_add", methods=['GET', 'POST'])
def bulk_add():
    if not session.get('logged_in'):
        flash('Пожалуйста, войдите, чтобы получить доступ к этой странице.', 'danger')
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не найден', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
        if file and file.filename.endswith('.csv'):
            try:
                stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                csv_input = csv.reader(stream)
                # Skip header row
                next(csv_input, None)
                for row in csv_input:
                    # Assuming CSV format: name,price,description,image_file,brand
                    name, price, description, image_file, brand = row
                    product = Product(name=name,
                                      price=float(price),
                                      description=description,
                                      image_file=image_file,
                                      brand=brand)
                    db.session.add(product)
                db.session.commit()
                flash('Товары из файла были успешно добавлены!', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Произошла ошибка при обработке файла: {e}', 'danger')
        else:
            flash('Пожалуйста, загрузите CSV файл.', 'danger')

    return render_template('bulk_add.html', title='Массовое добавление товаров')

@app.route("/admin_logout")
def admin_logout():
    session.pop('logged_in', None)
    flash('Вы вышли из админ-панели.', 'info')
    return redirect(url_for('home'))

@app.route("/remove_from_cart/<int:product_id>")
def remove_from_cart(product_id):
    if 'cart' in session:
        for item in session['cart']:
            if item['id'] == product_id:
                session['cart'].remove(item)
                session.modified = True
                flash('Товар удален из корзины!', 'success')
                break
    return redirect(url_for('cart'))

def init_db():
    with app.app_context():
        db.create_all()
        if not Product.query.first():
            product1 = Product(name='Футбольная форма Реал Мадрид', price=79.99, description='Домашняя форма сезона 2024/25', image_file='psg.jpg', brand='Adidas')
            product2 = Product(name='Футбольная форма Барселона', price=75.00, description='Выездная форма сезона 2024/25', image_file='psg.jpg', brand='Nike')
            product3 = Product(name='Футбольная форма Манчестер Юнайтед', price=82.50, description='Домашняя форма сезона 2024/25', image_file='psg.jpg', brand='Adidas')
            product4 = Product(name='Футбольная форма Бавария Мюнхен', price=78.00, description='Домашняя форма сезона 2024/25', image_file='psg.jpg', brand='Adidas')
            product5 = Product(name='Футбольная форма ПСЖ', price=76.00, description='Выездная форма сезона 2024/25', image_file='psg.jpg', brand='Nike')
            product6 = Product(name='Футбольная форма ПСЖ (гостевая)', price=79.00, description='Гостевая форма сезона 2024/25', image_file='psg.jpg', brand='Nike')
            db.session.add_all([product1, product2, product3, product4, product5, product6])
            db.session.commit()
        click.echo('Initialized the database.')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
