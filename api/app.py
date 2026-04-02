import os
import json
import re
import pandas as pd
from flask import Flask, render_template, redirect, jsonify, request, url_for, session, g, abort
from api.models import db, User, CartItem
import api.googleSheet as google_api
from dotenv import load_dotenv
from api.oauth import init_oauth, get_cred
from api.decorators import login_required, token_required

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)

# =============================================================================
#                        ## SETTING UP APP ##
# =============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///project.db")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(parent_dir, '.flask_session')
app.config['SESSION_PERMANENT'] = False
db.init_app(app)

google = init_oauth(app)
df = pd.DataFrame()
CATEGORY_MAP = {}
CATEGORIES = []
LEVELS = {"Levels": []}

# =============================================================================
#                             ## APP ROUTES ##
# =============================================================================

@app.route("/")
@app.route("/home")
def home():
    return render_template('home.html')

@app.route("/about")
def about():
    return redirect(os.getenv("ABOUT_PAGE_LINK"))


# ============================== Logging ======================================
@app.route("/login")
def login():
    return google.authorize_redirect(url_for("callback", _external=True))

@app.route("/login/callback")
def callback():
    token = google.authorize_access_token()
    user_info = google.get("userinfo").json()
    session["user"] = user_info
    session["token"] = token

    user = get_user_by_email(user_info["email"]) #Checking if user exists
    if not user:
        user = create_new_user(email=user_info["email"], name=user_info["name"]) #Create new user
        session['cart'] = []
    else:
        session["cart"] = [str(item.item_id) for item in user.cart_items]

    return redirect("/")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# =============================== Cart Routes =================================
# Display the user's cart
@app.route('/cart', methods = ["GET", 'POST'])
@login_required
def view_cart():
    return render_template('cartView.html')

# Get the size of the user's cart
@app.route('/getCartSize', methods=["POST"])
def cartSize():
    if g.user:
        return jsonify({'cart_count': len(g.user.cart_items)})
    return jsonify({'cart_count': 0})

# Add an item to the user's cart
@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    questionId = request.get_json()['question_id']
    message = ''

    if not get_cart_item(g.user, int(questionId)):
        new_cart_item = CartItem(user_id=g.user.id, item_id=int(questionId))
        update_db("add", new_cart_item)
        message = 'Question added to cart successfully!'
    else:
        message = 'Already in cart!'

    return jsonify({
        'message': message,
        'cart_count': len(g.user.cart_items)
    })

# Remove an item from the user's cart
@app.route('/removeItem', methods=['POST'])
@login_required
def removeItem():
    itemId = request.get_json()['id']
    cart_item = get_cart_item(g.user, int(itemId))

    if cart_item:
        update_db("delete", cart_item)
    return jsonify({'cart-count': len(g.user.cart_items)})

# =============================================================================
#                             ## JS CALL ROUTES ##
# =============================================================================

# Main function to get questions based on filters, search, and sort options. 
# Returns the questions in a format that can be easily rendered by the frontend.
@app.route("/questions", methods = ["GET", "POST"])
def showQuestions():
    Qs = pd.DataFrame()
    order = None
    search_term = request.args.get('searchQuery', '').lower()

    if request.method == "POST":
        subCategory, level, category, order = get_request_form_list(request, ['sub_category', 'level', 'category', 'orderBy'])
        Qs = apply_filters(df, category, subCategory, level)

    if Qs.empty: #Default fallback
        Qs = df.copy()

    Qs = apply_search(Qs, search_term)
    Qs = apply_sort(Qs, order)
    questions = Qs.to_dict(orient='records')
    return render_template('itemView.html', levels=LEVELS, categoryMap=CATEGORY_MAP, questions=questions)

# Function called by JS to get items in the cart
@app.route('/cartView', methods = ["POST"])
@login_required
def cartView():
    items = []
    cart_items = CartItem.query.filter_by(user_id=g.user.id).all()
    for item in cart_items:
        question = df[df['id'] == item.item_id].iloc[0]
        new_item = {
            'title': question['Item Stem'],
            'description': question['Anchors'].split(';'),
            'path': question['Category'] + " - " + question['Sub-Category'],
            'id': int(question['id']),
            "level": question["Levels"]
        }
        items.append(new_item)
    return jsonify(items)

# Function called by JS to get all question data
@app.route('/getData', methods=["POST"])
def getData():
    return jsonify(df.to_dict(orient='records'))

# Function called by JS to export cart to preferred destination
@app.route('/exporting', methods=["POST"])
@token_required
def exporting():
    dest = request.form.get('dest')
    data = json.loads(request.form.get('data'))
    creds = get_cred(session["token"])
    questions = pd.DataFrame()

    for item in data:
        questions = pd.concat([questions, df[(df["id"] == int(item))]])

    export_to(destination=dest, data=questions, creds=creds, user=g.user)

# Function called by JS to get summary of items in the cart listed in order by levels
@app.route('/getSummary', methods=["POST"])
@login_required
def getSummary():
    levels_in_cart = []    # Initialize a list to store the levels of items in the cart

    cart_items = CartItem.query.filter_by(user_id=g.user.id).all()
    for item in cart_items:
        question = df[df['id'] == item.item_id].iloc[0]
        levels_in_cart.append(question['Levels'])

    levels_counts = pd.Series(levels_in_cart).value_counts().to_dict()

    return jsonify(levels_counts)

# =============================================================================
#                             ## HELPER FUNCTIONS ##
# =============================================================================

def create_new_user(email, name, doc=None, form=None):
    user = User(email=email, name=name, doc=doc, form=form)
    update_db("add", user)
    return user

def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def get_request_form_list(request, fields):
    return [request.form.getlist(field) if request.form.getlist(field) else [] for field in fields]

def update_db(method, element):
    if method == "add":
        db.session.add(element)
    elif method == "delete":
        db.session.delete(element)
    db.session.commit()

def export_to(destination, data, creds, user):
    if destination == 'forms':
        if user.form:
            form = google_api.update_form(data, creds, user.form)
        else:
            form = google_api.update_form(data, creds, None)
            user.form = form
            db.session.commit()
        return redirect('https://docs.google.com/forms/d/' + form)
    else:
        if user.doc:
            docId = google_api.create_doc(data, creds, user.doc)
        else:
            docId = google_api.create_doc(data, creds, None)
            user.doc = docId
            db.session.commit()
        return redirect('https://docs.google.com/document/d/' + docId)

def get_cart_item(user, item_id):
    return CartItem.query.filter_by(user_id=user.id, item_id=item_id).first()

def custom_sort(val):
    level_match = re.match(r'Level (\d)', val)
    if level_match:
        return (0, int(level_match.group(1)))  # Prioritize levels by numeric value
    else:
        return (1, val)  # Alphabetical order for non-levels

def apply_search(Qs, search_term):
    if search_term:
        Qs = Qs[Qs["Item Stem"].str.lower().str.contains(search_term, regex=False)]
    return Qs

def apply_sort(qs, order):
    if not order:
        return qs
    if order[0] == "lev":
        return qs.sort_values(by="Levels", key=lambda x: x.map(custom_sort))
    else:
        return qs.sort_values(by="Sub-Category")
    
def apply_filters(df, categories, subcategories, levels):
    mask = pd.Series(True, index=df.index)
    if categories:
        mask &= df["Category"].isin(categories)
    if subcategories:
        mask &= df["Sub-Category"].isin(subcategories)
    if levels:
        mask &= df["Levels"].isin(levels)
    return df[mask].copy() # Makes sure there is no accidental mutation