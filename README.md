# A1_web_development
A photo browsing website, a project for ece1779
All those instructions below are tested to work fine on Ubuntu 16.04

1.install python 3.5, mysql, mysql-workbench, mysql-connector-python on your machine

2.navigate into the project folder 'photo_browse', and create a virtual environment
$ python3 -m venv flask

3.activate the venv
$ source flask/bin/activate

4.install flask and wand(an ImageMagick binding for python)
$ flask/bin/pip install flask
$ sudo apt-get install python3-wand

5.use mysql-workbench to run sql script 'photo_browser_sql.sql', creating a database for use

6.change the value of 'password' in app/config.py to your mysql password

7.run
$ python3 run.py
