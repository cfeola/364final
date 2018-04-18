############################
# Import statements
############################
import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, RadioField, TextAreaField, FileField, PasswordField, BooleanField, SelectMultipleField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from werkzeug.security import generate_password_hash, check_password_hash
import requests 
import json 
from recipe_api import app_id, api_key, api_url

# Imports for login management
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash

############################
# Application configurations
############################
app = Flask(__name__)
app.debug = True
app.use_reloader = True
app.config['SECRET_KEY'] = 'hard to guess string from si364'
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost/SI364FinalProjectcfeola"
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

##################
### App setup ####
##################
manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)


# Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) 

#########################
##### Set up Models #####
#########################
# TODO 364: Set up association Table between search terms and Recipes (you can call it anything you want, we suggest 'tags' or 'search_gifs').
search_recipes = db.Table('search_recipes', db.Column('recipesearch_id', db.Integer,db.ForeignKey('recipesearch.id')),db.Column('recipe_id',db.Integer,db.ForeignKey('recipe.id')))
#  Sets up the association table between recipes and recipe collections created by user
recipe_book = db.Table('recipe_book', db.Column('recipe_id', db.Integer,db.ForeignKey('recipe.id')),db.Column('personalrecipebook_id',db.Integer,db.ForeignKey('personalrecipebook.id')))

# Database model that stores user login information
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    recipes = db.relationship('PersonalRecipeBook',backref='User')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

## DB load function
## Necessary for behind the scenes login manager that comes with flask_login capabilities! Won't run without this.
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Database model to store recipes
class Recipe(db.Model):
    __tablename__ = "recipe"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000))
    labels = db.Column(db.String(1000))
    ingredients = db.Column(db.String(1000))
    image = db.Column(db.String(1000))
    url = db.Column(db.String(1000))


# Database model to store personal recipe books
class PersonalRecipeBook(db.Model):
    __tablename__ = "personalrecipebook"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))

    # A one-to-many relationship with the User model (one user, many personal collections of recipes)
    User_id = db.Column(db.Integer, db.ForeignKey('users.id')) 

    # A many to many relationship with the Recipe model (one recipe might be in many personal recipe collections, one personal recipe collection could have many recipes in it)
    recipes = db.relationship('Recipe',secondary=recipe_book, backref=db.backref('personalrecipebook',lazy='dynamic'),lazy='dynamic')

class RecipeSearch(db.Model):
    __tablename__ = "recipesearch"
    id = db.Column(db.Integer, primary_key=True)
    search = db.Column(db.String(128))
    diet = db.Column(db.String(128))
    health = db.Column(db.String(128))
    calories = db.Column(db.String(128))

    recipes = db.relationship('Recipe',secondary=search_recipes, backref=db.backref('recipesearch',lazy='dynamic'),lazy='dynamic')

    # TODO 364: Define a __repr__ method for this model class that returns the term string
    def __repr__(self):
        return "{}".format(self.search)

class SiteEvaluation(db.Model):
    __tablename__ = "siteevaluation"
    id = db.Column(db.Integer, primary_key=True)
    experience = db.Column(db.String(128))
    explaination = db.Column(db.String(500))
    name = db.Column(db.String(500))
    email = db.Column(db.String(500))    

    def __repr__(self):
        return "{} (ID: {})".format(self.explaination, self.id)

    def __init__(self, experience,explaination,name,email):
        self.experience = experience
        self.explaination = explaination
        self.name = name
        self.email = email

########################
##### Set up Forms #####
########################

# Registration form for new users
class RegistrationForm(FlaskForm):
    email = StringField('Email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm Password:",validators=[Required()])
    submit = SubmitField('Register User')

    #Additional checking methods for the form
    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

# Login form for current users
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

# Recipe search form for main page of app
class RecipeSearchForm(FlaskForm):
    search = StringField("Enter a term to search for a recipe", validators=[Required()])
    diet = RadioField("Select one dietary restriction", choices = [("balanced","balanced"),("high-protein","high-protein"),("low-fat","low-fat"),("low-carb","low-carb")],validators=[Required()])
    health = RadioField("Select one health restriction", choices = [("vegan","vegan"),("vegetarian","vegetarian"),("sugar-conscious","sugar-conscious"),("peanut-free","peanut-free"),("tree-nut-free","tree-nut-free"),("alcohol-free","alcohol-free")],validators=[Required()])
    calories = StringField("Enter a range for calories (min-max)", validators=[Required()])
    submit = SubmitField('Submit')

    def validate_search(self, field):
        if not field.data.isalpha():
            raise ValidationError("Please enter a search term only containing letters.")
    def validate_calories(self,field):
        if '-' not in field.data:
            raise ValidationError("Please enter a range for calories in the format of min-max.")


# Form to personal create recipe books for current users that are logged in 
class CreateRecipeBookForm(FlaskForm):
    name = StringField('Recipe Collection Name',validators=[Required()])
    recipe_picks = SelectMultipleField('Recipes to include',coerce=int)
    submit = SubmitField("Create Recipe Collection")

class UpdateButtonForm(FlaskForm):
    submit = SubmitField('Update Recipe Book Name')

class UpdateBookTitle(FlaskForm):
    new_book_name = StringField("Enter a new name for the recipe book", validators=[Required()])
    submit = SubmitField("Update Recipe Book Name")

class DeleteButtonForm(FlaskForm):
    submit = SubmitField('Delete')

class Evaluation(FlaskForm):
    evaluation = RadioField("Did you have a positive experience using our website?", choices=[('Yes','Yes'),('No','No')], validators=[Required()])
    explaination = StringField("Briefly explain why you chose the answer above.",validators=[Required()])
    name = StringField("Name: ")
    email = StringField("E-mail: ")
    submit = SubmitField()

################################
####### Helper Functions #######
################################

def get_recipe_by_id(id):
    """Should return recipe object or None"""
    r = Recipe.query.filter_by(id=id).first()
    return r

def get_recipes_from_api(recipe_search,diet_search,health_search,calories_range):
    """ Returns data from Recipe API with up to 5 recipes corresponding to the search input"""
    params_dict = {'app_id':app_id, 'app_key': api_key,'q':recipe_search,'diet':diet_search, 'health':health_search, 'calories':calories_range,'to':5}
    resp = requests.get(api_url, params = params_dict)
    data = json.loads(resp.text)

    # Iterates through the first 5 search results and returns the names of those recipes 
    recipe_names = {}
    for recipe in data['hits']:
        recipe_names[recipe['recipe']['label']] = (recipe['recipe']['healthLabels'],recipe['recipe']['ingredientLines'],recipe['recipe']['image'],recipe['recipe']['url'])
    return(recipe_names)

def get_or_create_recipe(name,labels_list,ingredients_list,image_url,recipe_url):
    print(labels_list)
    print(ingredients_list)
    labels_string = ','.join(labels_list)
    ingredients_string = ','.join(ingredients_list)

    recipe = Recipe.query.filter_by(name=name,labels=labels_string,ingredients=ingredients_string, image=image_url,url = recipe_url).first()
    if recipe:
        return recipe
    else:
        new_recipe = Recipe(name=name,labels=labels_string,ingredients=ingredients_string,image=image_url,url = recipe_url)
        db.session.add(new_recipe)
        db.session.commit()
        return new_recipe

def get_or_create_recipebook(name, current_user, recipe_list=[]):   
    user_id = User.query.filter_by(username=current_user).first().id
    recipe_book = PersonalRecipeBook.query.filter_by(name=name, User_id = user_id).first()
    if not recipe_book:
        new_recipe_book = PersonalRecipeBook(name=name, User_id = user_id)
        db.session.add(new_recipe_book)
        db.session.commit()
        for recipe in recipe_list:
            new_recipe_book.recipes.append(recipe)
        return(new_recipe_book)
    else:
        return(recipe_book)


###################################
##### Routes & view functions #####
###################################

# Error handling route 
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Error handling route 
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# Should render form for logging in to app. When the form is submitted, checks to see that the user 
# exists and that they have entered the correct password. If they did, their login information is 
# remembered by the browser and they are redirected to the home page of the site. If they entered
# incorrect information, an error message flashes and they are redirected back to the login page.
@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)

# When the user attempts to log out, a message flashes letting them know they have successfully logged
# out and they are redirected to the home page of the site. 
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))

# Should render the registration form for new users to the site. When the form is submitted, 
# the user's information is added and committed to the database and redirects to the login page 
# where they can login to the app 
@app.route('/register',methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in!')
        return redirect(url_for('login'))
    flash('That email and/or username is already in use. Please use a different email and/or username.')
    return render_template('register.html',form=form)

# Should render the RecipeSearchForm where users are able to enter a search term, select multiple
# dietary and health restrictions, and enter a range of calories (min-max) to find a desired recipe.
# This function makes a call to the Recipe API and returns the top 5 search results that best 
# match the users search criteria 
@app.route('/', methods=['GET', 'POST'])
def index():
    form = RecipeSearchForm()
    if form.validate_on_submit():
        recipe_search = form.search.data
        print(recipe_search)
        diet_search = form.diet.data
        print(diet_search)
        health_search = form.health.data
        print(health_search)
        calories_range = form.calories.data
        print(calories_range)
       
        search = RecipeSearch.query.filter_by(search=recipe_search, diet = diet_search, health = health_search, calories = calories_range).first()
        if not search:
            new_search = RecipeSearch(search=recipe_search, diet = diet_search, health = health_search, calories = calories_range)
            db.session.add(new_search)
            db.session.commit()

        recipe_dict = get_recipes_from_api(recipe_search,diet_search,health_search,calories_range)
        print(recipe_dict)
        for recipe in recipe_dict:
            recipe_return = get_or_create_recipe(recipe,recipe_dict[recipe][0],recipe_dict[recipe][1],recipe_dict[recipe][2],recipe_dict[recipe][3])
            new_search.recipes.append(recipe_return)

        return render_template('search_results.html',data=recipe_dict)
    else:
        errors = [v for v in form.errors.values()]
        if len(errors) > 0:
            flash("!!!! ERRORS IN FORM SUBMISSION - " + str(errors))
        return(render_template('base.html', form = form))

# Should render a template that displays all search terms (from all users) that are currently in the database
# and 5 recipes that resulted from each of those searches
@app.route('/search_terms')
def all_search_terms():
    search_terms = RecipeSearch.query.all()
    return render_template('search_terms.html',search_terms=search_terms)

# Should render a template that displays all recipes (from all users) that are currently in the database
@app.route('/all_recipes')
def all_recipes():
    all_recipes = Recipe.query.all()
    return render_template('all_recipes.html',all_recipes=all_recipes)

# Should render a template that allows a user to create a recipe book containing any combination 
# of recipes that are currently in the database. Once the form is submitted, the user is redirected
# to list of all recipe books the current user created 
@app.route('/create_recipe_book',methods=["GET","POST"])
@login_required
def create_recipe_book():
    form = CreateRecipeBookForm()
    recipes = Recipe.query.all()
    choices = [(r.id, r.name) for r in recipes]
    form.recipe_picks.choices = choices
    
    if form.validate_on_submit():
        name = form.name.data
        picks = form.recipe_picks.data
      
        recipe_object_list = []
        for each in picks:
            obj = get_recipe_by_id(each)
            recipe_object_list.append(obj)

        print(current_user.username)
        get_or_create_recipebook(name = name, current_user = current_user.username,recipe_list = recipe_object_list)
        return redirect(url_for('recipe_books'))
    return render_template('create_recipe_book.html',form=form)

# Should render a template that displays all of the recipe books that the current user has created
@app.route('/recipe_books',methods=["GET","POST"])
@login_required
def recipe_books():
    form = DeleteButtonForm()
    recipe_books = PersonalRecipeBook.query.filter_by(User_id = current_user.id).all()
    return render_template('recipe_books.html', recipe_books = recipe_books,form=form)

# Should render a template that displays one specific recipe book that the current user has created
@app.route('/recipe_book/<id_num>')
@login_required
def recipe_book(id_num):
    form = UpdateButtonForm()
    id_num = int(id_num)
    recipe_book = PersonalRecipeBook.query.filter_by(id=id_num).first()
    recipes = recipe_book.recipes.all()
    return render_template('recipe_book.html',recipe_book=recipe_book, recipes=recipes,form=form)

# Allows user to update the name of their personal recipe book
@app.route('/update/<book>',methods=["GET","POST"])
def update(book):
    form = UpdateBookTitle()
    if form.validate_on_submit():
        new_book_name = form.new_book_name.data
        x = PersonalRecipeBook.query.filter_by(name = book).first()
        x.name = new_book_name
        db.session.commit()
        flash("Updated name of " + book)
        return redirect(url_for('recipe_books'))
    return render_template('update_name.html', book_name =  book, form = form)

# Allows user to delete their personal recipe book from the database
@app.route('/delete/<book>',methods=["GET","POST"])
def delete(book):
    recipe_book = PersonalRecipeBook.query.filter_by(name = book).first()
    db.session.delete(recipe_book)
    db.session.commit()
    flash("Deleted list " + book)
    return redirect(url_for('recipe_books'))

# Renders a template that allows the user to evaluate the site
@app.route('/eval',methods=['GET','POST'])
def eval():
    form = Evaluation()
    return render_template('eval.html',form=form)

# If the users evaluation form validates upon submit, their response is saved into the database 
# and they are redirected to a thank you page 
@app.route('/evalResults',methods=['GET','POST'])
def evalResults():
    form = Evaluation()
    if request.args:
        experience = request.args.get('evaluation')
        explaination = request.args.get('explaination')
        name = request.args.get('name')
        email = request.args.get('email')

        person = SiteEvaluation.query.filter_by(email=email).first()
        if not person:
            new_eval = SiteEvaluation(experience=experience,explaination=explaination, name = name, email = email)
            db.session.add(new_eval)
            db.session.commit()
            return render_template('thanks.html')
        else:
            flash("You have already submitted feedback. Sorry, you can only submit feedback once.")
            return render_template('thanks.html')
    return redirect(url_for('eval'))

if __name__ == "__main__":
    db.create_all()
    manager.run()
