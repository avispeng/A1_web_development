from flask import render_template, redirect, url_for, request, g, session
from app import webapp
import random
import hashlib
import mysql.connector
from app.config import db_config
import os
from wand.image import Image

webapp.secret_key = os.urandom(24)

@webapp.route('/',methods=['GET'])
@webapp.route('/index',methods=['GET'])
# Display an HTML page with links
def main():
    return render_template("main.html",title="Photos Browser")


def connect_to_database():
    return mysql.connector.connect(user=db_config['user'],
                                   password=db_config['password'],
                                   host=db_config['host'],
                                   database=db_config['database'])


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect_to_database()
    return db


@webapp.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@webapp.route('/index/login', methods=['POST'])
def user_login():
    username = request.form.get('usrn',"")
    pwd = request.form.get('pwd',"")

    #check if the account exists
    cnx = get_db()
    cursor = cnx.cursor(buffered=True)
    query = '''SELECT hashed_pwd, salt FROM users WHERE username = %s'''
    cursor.execute(query,(username,))
    row = cursor.fetchone()

    error = False
    if row is None:
        error=True
        error_msg = "Error: Username doesn't exist!"
    if error:
        return render_template("main.html",title="Photo Browser", login_error_msg=error_msg, log_username=username)

    # if username exists, is pwd correct?
    salt = row[1]
    hashed_pwd = row[0]
    pwd += salt
    if hashed_pwd == hashlib.sha256(pwd.encode()).hexdigest():
        # add to the session
        session['username'] = username
        return redirect(url_for('home_page', username=username))
    else:
        error=True
        error_msg = "Error: Wrong password or username! Please try again!"
    if error:
        return render_template("main.html",title="Photo Browser", login_error_msg=error_msg, log_username=username)


@webapp.route('/index/register', methods=['POST'])
def user_signup():
    username = request.form.get('newusrn')
    pwd = request.form.get('newpwd')

    # check length of input
    error = False
    if len(username)<6 or len(username)>20 or len(pwd)<6 or len(pwd)>20:
        error=True
        error_msg = "Error: Both username and password should have length of 6 to 20!"
    if error:
        return render_template("main.html",title="Photo Browser", signup_error_msg=error_msg, sign_username=username)

    cnx = get_db()
    cursor = cnx.cursor(buffered=True)

    # check whether username exists
    query = '''SELECT * FROM users WHERE username = %s'''
    cursor.execute(query,(username,))
    row = cursor.fetchone()
    error = False
    if row is not None:
        error=True
        error_msg = "Error: Username already exists!"
    if error:
        return render_template("main.html", title="Photo Browser", signup_error_msg=error_msg, sign_username=username)

    # create a salt value
    ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    chars=[]
    for i in range(8):
        chars.append(random.choice(ALPHABET))
    salt = "".join(chars)
    pwd += salt
    hashed_pwd = hashlib.sha256(pwd.encode()).hexdigest()

    query = '''INSERT INTO users (user_id, username, hashed_pwd, salt)
    VALUES (NULL, %s, %s, %s)'''
    cursor.execute(query, (username, hashed_pwd, salt))
    cnx.commit()
    # add to the session
    session['username'] = username
    return redirect(url_for('home_page', username=username))


@webapp.route('/home/<username>', methods=['GET'])
def home_page(username):
    # make sure the user is the one logging in the session
    if 'username' not in session:
        return redirect(url_for('main'))
    if session['username']!=username:
        return redirect(url_for('home_page',username=session['username']))

    cnx = get_db()
    cursor = cnx.cursor(buffered=True)
    fpath = './app/static/photos/{}'.format(username)
    if not os.path.exists(fpath):
        os.makedirs(fpath)
    query = '''SELECT images.img_id, images.img_name, images.filename FROM images, 
    users WHERE users.username = %s AND images.owned_by = users.user_id'''
    cursor.execute(query, (username,))  # current login user

    return render_template("home.html", title="Your photos", cursor=cursor, username=username, fpath=fpath)


@webapp.route('/home/<username>/logout', methods=['GET'])
def logout(username):
    session.pop('username', None)
    return redirect(url_for('main'))


@webapp.route('/home/<username>/<int:img_id>', methods=['GET'])
def image_display(username, img_id):
    # make sure the user is the one logging in the session
    if 'username' not in session:
        return redirect(url_for('main'))
    if session['username']!=username:
        return redirect(url_for('home_page',username=session['username']))
    cnx = get_db()
    cursor = cnx.cursor(buffered=True)
    query = "SELECT img_name, location, description, owned_by, filename FROM images WHERE img_id = %s"
    cursor.execute(query,(img_id,))
    row = cursor.fetchone()
    name = row[0]
    location = row[1]
    desc = row[2]
    owner = row[3]
    filename = row[4]
    # make sure the user unable to see others' photos via entering URL
    query = "SELECT username FROM users WHERE user_id = %s"
    cursor.execute(query,(owner,))
    if cursor.fetchone()[0] != username:
        return redirect(url_for('home_page', username=session['username']))
    return render_template("image_display.html", title="Photo display",img_id=img_id,
                           img_name=name, location=location, description = desc, filename=filename, username=username)


@webapp.route('/home/<username>/upload', methods=['GET'])
def file_upload(username):
    # make sure the user is the one logging in the session
    if 'username' not in session:
        return redirect(url_for('main'))
    if session['username'] != username:
        return redirect(url_for('home_page', username=session['username']))
    return render_template("file_upload.html", title="Upload your photo", username=username)


@webapp.route('/home/<username>/upload', methods=['POST'])
def file_uploaded(username):
    # make sure the user is the one logging in the session
    if 'username' not in session:
        return redirect(url_for('main'))
    if session['username'] != username:
        return redirect(url_for('home_page', username=session['username']))

    # where to store the image
    fpath = './app/static/photos/{}'.format(username)
    allowed_ext = set(['jpg','jpeg','png','gif'])
    f = request.files['myFile']
    fn = f.filename
    # handling filename length
    if len(fn) > 30:
        try:
            rez = fn.split(".")
            fn = rez[0][0:15] + "." + rez[1]
            print("fn formatted is: " + fn)
        except:
            # invalid file input
            return redirect(url_for('home_page', username=session['username']))

    img_name = request.form.get('img_name',"")
    if img_name == "":
        img_name = fn
    if len(img_name)>20:
        img_name = img_name[:20]
    location = request.form.get('location',"")
    description = request.form.get('description',"")
    if '.' in fn and fn.rsplit('.',1)[1].lower() in allowed_ext:
        f.save(os.path.join(fpath, fn))
        with Image(filename=os.path.join(fpath, fn)) as img:
            size = img.size
            with img.convert('jpg') as converted1:
                # create thumbnail
                if size[0] < size[1]:
                    converted1.crop(0, (size[1] - size[0]) // 2, width=size[0], height=size[0])
                else:
                    converted1.crop((size[0] - size[1]) // 2, 0, width=size[1], height=size[1])
                converted1.sample(150, 150)
                converted1.save(filename=os.path.join(fpath, "thumbnail_"+fn))
            with img.convert('jpg') as converted2:
                # scale up
                converted2.resize(int(size[0]*1.2), int(size[1]*1.2))
                converted2.save(filename=os.path.join(fpath, "scaleup_"+fn))
            with img.convert('jpg') as converted3:
                # scale down
                converted3.resize(int(size[0] * 0.8), int(size[1] * 0.8))
                converted3.save(filename=os.path.join(fpath, "scaledown_" + fn))
            with img.convert('jpg') as converted4:
                # grayscale
                converted4.type = 'grayscale'
                converted4.save(filename=os.path.join(fpath, "grayscale_" + fn))

        cnx = get_db()
        cursor = cnx.cursor(buffered=True)
        query = '''SELECT user_id FROM users WHERE username = %s'''
        cursor.execute(query,(username,))
        user_id = cursor.fetchone()[0]
        query = '''INSERT INTO images (img_id, img_name, location, description, owned_by, filename)
        VALUES (NULL, %s, %s, %s, %s, %s)'''
        cursor.execute(query,(img_name, location, description, user_id, fn))
        cnx.commit()
        return redirect(url_for('home_page',username=username))
    else:
        error = True
        error_msg = "Error: Invalid photo format! Please choose from jpg, jpeg, gif, png!"
        if error:
            return render_template("file_upload.html", title="Upload your photo", username=username, error_message=error_msg)


@webapp.route('/test/FileUpload', methods=['GET','POST'])
def test_file_upload():
    if request.method == 'GET':
        return render_template("for_test.html", title="File Upload Test")

    if request.method == 'POST':
        username = request.form.get('usrn', "")
        pwd = request.form.get('pwd', "")

        # check if the account exists
        cnx = get_db()
        cursor = cnx.cursor(buffered=True)
        query = '''SELECT hashed_pwd, salt FROM users WHERE username = %s'''
        cursor.execute(query, (username,))
        row = cursor.fetchone()

        error = False
        if row is None:
            error = True
            error_msg = "Error: Username doesn't exist!"
        if error:
            return render_template("for_test.html", title="File Upload Test", login_error_msg=error_msg, log_username=username)

        # if username exists, is pwd correct?
        salt = row[1]
        hashed_pwd = row[0]
        pwd += salt
        if hashed_pwd == hashlib.sha256(pwd.encode()).hexdigest():
            # add to the session
            session['username'] = username
            fpath = './app/static/photos/{}'.format(username)
            allowed_ext = set(['jpg', 'jpeg', 'png', 'gif'])
            f = request.files['myFile']
            fn = f.filename
            img_name = request.form.get('img_name', "")
            if img_name == "":
                img_name = fn
            if len(img_name) > 20:
                img_name = img_name[:20]
            location = request.form.get('location', "")
            description = request.form.get('description', "")
            if '.' in fn and fn.rsplit('.', 1)[1].lower() in allowed_ext:
                f.save(os.path.join(fpath, fn))
                with Image(filename=os.path.join(fpath, fn)) as img:
                    size = img.size
                    with img.convert('jpg') as converted1:
                        # create thumbnail
                        if size[0] < size[1]:
                            converted1.crop((0, size[1] - size[0]) // 2, width=size[0], height=size[0])
                        else:
                            converted1.crop((size[0] - size[1]) // 2, 0, width=size[1], height=size[1])
                        converted1.sample(150, 150)
                        converted1.save(filename=os.path.join(fpath, "thumbnail_" + fn))
                    with img.convert('jpg') as converted2:
                        # scale up
                        converted2.resize(int(size[0] * 1.2), int(size[1] * 1.2))
                        converted2.save(filename=os.path.join(fpath, "scaleup_" + fn))
                    with img.convert('jpg') as converted3:
                        # scale down
                        converted3.resize(int(size[0] * 0.8), int(size[1] * 0.8))
                        converted3.save(filename=os.path.join(fpath, "scaledown_" + fn))
                    with img.convert('jpg') as converted4:
                        # grayscale
                        converted4.type = 'grayscale'
                        converted4.save(filename=os.path.join(fpath, "grayscale_" + fn))

                cnx = get_db()
                cursor = cnx.cursor(buffered=True)
                query = '''SELECT user_id FROM users WHERE username = %s'''
                cursor.execute(query, (username,))
                user_id = cursor.fetchone()[0]
                query = '''INSERT INTO images (img_id, img_name, location, description, owned_by, filename)
                    VALUES (NULL, %s, %s, %s, %s, %s)'''
                cursor.execute(query, (img_name, location, description, user_id, fn))
                cnx.commit()
                return redirect(url_for('home_page', username=username))
            else:
                error = True
                error_msg = "Error: Invalid photo format! Please choose from jpg, jpeg, gif, png!"
                if error:
                    return render_template("for_test.html", title="File Upload Test", login_error_msg=error_msg,
                                           log_username=username)
        else:
            error = True
            error_msg = "Error: Wrong password or username! Please try again!"
        if error:
            return render_template("for_test.html", title="File Upload Test", login_error_msg=error_msg, log_username=username)
