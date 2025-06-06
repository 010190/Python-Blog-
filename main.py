from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request, current_app
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey, insert, engine
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms.fields.simple import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
import os
from dotenv import find_dotenv, load_dotenv


dotenv_path = find_dotenv()

load_dotenv(dotenv_path)

SECRET_KEY = os.getenv('SECRET_KEY')
DB = os.getenv('DB')


# Import your forms from the forms.py
from forms import CreatePostForm, CreateCommentForm


'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''
login_manager = LoginManager()
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
ckeditor = CKEditor(app)
login_manager.init_app(app)
Bootstrap5(app)


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)
# TODO: Configure Flask-Login

class RegisterForm(FlaskForm):
    name  = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')




# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = DB
db = SQLAlchemy(model_class=Base)
db.init_app(app)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(250), nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)

    posts = relationship("BlogPost", back_populates="author")

    comments = relationship("Comment", back_populates="author")

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    author = relationship("User", back_populates="posts")
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))

    comments = relationship("Comment", back_populates="post")
    # Create reference to the User object. The "posts" refers to the posts property in the User class.

class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    author = relationship("User", back_populates="comments")
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))

    post = relationship("BlogPost", back_populates="comments")
    post_id : Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))

# TODO: Create a User table for all your registered users. 

def admin_only(f):
    @wraps(f)
    def decorated_view(*args, **kwargs):
        if current_user.id != 1:
            return login_manager.unauthorized()

        return f(*args, **kwargs)

    return decorated_view


def logged_only(f):
    @wraps(f)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("You must be logged in to view this page.")
            return redirect(url_for('login'))

        return f(*args, **kwargs)

    return decorated_view



@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

with app.app_context():
    db.create_all()


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=['GET', 'POST'])
def register():
    logout_user()
    form = RegisterForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user:
            flash('Email already registered.')
            return redirect(url_for('login'))
        else:
            with app.app_context():
                new_user = User(
                    name = request.form.get("name"),
                    email = request.form.get("email"),
                    password=generate_password_hash(password=request.form.get('password'), method="pbkdf2:sha256",
                                                    salt_length=8)
                )
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET', 'POST'])
def login():
    logout_user()
    form = LoginForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            email = request.form.get('email')
            user = db.session.execute(db.select(User).where(User.email == email)).scalar()
            if user is None:
                flash('Email not found.')
                return redirect(url_for('login'))



            if check_password_hash(user.password,request.form.get('password')):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash('Password incorrect.')
                return redirect(url_for('login'))
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():

    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()

    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=['GET', 'POST'])

def show_post(post_id):
    form = CreateCommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You must be logged in comment.")
            return redirect(url_for('login'))
        else:
            with app.app_context():
                new_comment = Comment(
                    text=request.form.get("comment"),
                    author_id=current_user.id,
                    post_id=requested_post.id,

                )
                db.session.add(new_comment)
                db.session.commit()
            form = CreateCommentForm(formdata=None)
    comments = db.session.execute(db.select(Comment)).scalars().all()


    return render_template("post.html", post=requested_post, form=form, comments=comments)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False, port=5002)
