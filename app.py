import os
import subprocess
import openai

from flask import Flask, flash, request, redirect, url_for, render_template
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS




@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # file_path = ''

        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(os.getenv("PROJECT_DIR"), app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            # print(os.path.exists(os.path.join(os.getenv("PROJECT_DIR"), app.config['UPLOAD_FOLDER'], filename)))
            return processing_image(file_path)
            # return redirect(url_for('upload_file', result='processing'))

    result = request.args.get("result")
    return render_template("index.html", result=result)

def processing_image(file_path: os.path):
    subprocess.run(['handprint', file_path, '/s', 'microsoft', '/e','/j'])
    # print("done")
    return parsing(file_path)

def parsing(file_path: os.path):
    head, tail = os.path.split(file_path)
    new_tail = tail[:tail.rfind('.')] + ".handprint-microsoft.txt"
    new_file = os.path.join(head, new_tail)
    # print(os.path.join(head, new_tail))
    with open(new_file) as f:
        lines = f.readlines()
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=generate_prompt(lines),
            temperature=0,
        )
    print(response)
    return redirect(url_for("upload_file", result=response.choices[0].text))

def generate_prompt(lines):
    return '''
    doctor wrote a prescription, then it was read by neural network. Please extract from prescription name of medicine, how many times a day, how much, for how long, in the following format:
name of medicine | how many times a day | how much | for how long

Prescription
\'\'\'
{}
\'\'\'
    '''.format(lines)