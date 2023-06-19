import os
import subprocess
import openai
import json
import shutil
import time

from flask import Flask, flash, request, redirect, url_for, render_template
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.static_folder = os.path.join(os.getenv("PROJECT_DIR"), "static")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def word_distribution(new_file_json, ca_file):
    words = []
    with open(new_file_json) as f_json:
        json_file = json.load(f_json)
        for json_line in json_file["analyzeResult"]["readResults"][0]["lines"]:
            for word in json_line["words"]:
                words.append(Word(word["boundingBox"], word["text"]))

        words.sort(key=lambda word: word.center.y)

    text = []
    current_word_it = 0
    current_center = CurrentCenter(words[current_word_it].center, words[current_word_it].height)
    line = []
    line.append(words[current_word_it])

    while current_word_it < words.__len__() - 1:
        current_word_it += 1
        current_word = words[current_word_it]
        if current_word.center.y + current_word.height/3 > current_center.upper and current_word.center.y - current_word.height/3 < current_center.lower:
            current_center.append(current_word.center, current_word.height)
            line.append(current_word)
        else:
            text.append(line)
            line = []
            line.append(current_word)
            current_center = CurrentCenter(words[current_word_it].center, words[current_word_it].height)
    text.append(line)

    for line in text:
        line.sort(key=lambda word: word.center.x)

    lines = ''
    with open(ca_file, "w") as ca_f:
        for line in text:
            for word in line:
                lines += word.text + " "
                ca_f.write(word.text+" ")
            ca_f.write("\n")
            lines += "\n"

    return lines



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
            return redirect(url_for('processing_image', file_path=file_path))
            # return redirect(url_for('upload_file', result='processing'))

    result = request.args.get("result")
    file_path = request.args.get("file_path")

    new_file_path = ''
    result_lines = ''

    if file_path != None:
        head, tail = os.path.split(file_path)
        # RI_path = os.path.join("images", tail)
        new_file_path = tail[:tail.rfind('.')] + ".handprint-all.png"

        with open(file_path[:file_path.rfind('.')] + ".custom-alignment.txt") as CA_file:
            result_lines = CA_file.readlines()


    sum_str = ''
    for line in result_lines:
        sum_str += line

    return render_template("index.html", result=result, full_result=sum_str, recognized_image=new_file_path)

@app.route('/process', methods=['GET'])
def processing_image():
    file_path = request.args.get("file_path")
    start_handprint = time.time()
    subprocess.run(['handprint', file_path, '/d', 'text,bb-word,bb-line',  '/s', 'microsoft', '/e','/j'])
    end_handprint = time.time()
    print("Handprint has finished, time elapsed:", end_handprint-start_handprint)
    head, tail = os.path.split(file_path)
    src = file_path[:file_path.rfind('.')]+".handprint-all.png"
    print("src: ", src)
    shutil.copyfile(src, os.path.normpath(os.path.join(head, "..", "static", "images", os.path.basename(src))))
    return redirect(url_for("parsing", file_path=file_path))

@app.route('/parse', methods=['GET'])
def parsing():
    file_path = request.args.get("file_path")
    head, tail = os.path.split(file_path)
    ca_tail = tail[:tail.rfind('.')] + ".custom-alignment.txt"
    new_tail_json = tail[:tail.rfind('.')] + ".handprint-microsoft.json"
    ca_file = os.path.join(head, ca_tail)
    new_file_json = os.path.join(head, new_tail_json)

    start_word_distribution = time.time()
    lines = word_distribution(new_file_json, ca_file)
    end_word_distribution = time.time()
    print("Word distribution algorithm has finished, time elapsed:", end_word_distribution-start_word_distribution)

    start_gpt = time.time()
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=generate_prompt(lines),
        temperature=0,
    )
    end_gpt = time.time()
    print("Chat-GPT has finished, time elapsed:", end_gpt-start_gpt)
    # print(response)
    # fake_result="fake result"
    return redirect(url_for("upload_file", result=response.choices[0].text, file_path=file_path))
    # return redirect(url_for("upload_file", result=fake_result, file_path=file_path))

def generate_prompt(lines):
    return '''
Doctor wrote a prescription, then it was read by neural network. Prescription may have several medicines prescribed. Extract from prescription: name of medicine, how many times a day, how much, for how long.
Write it in the following format
1. name of first medicine | how many times a day | how much | for how long in days.
2. name of second medicine | how many times a day | how much | for how long in days.
...

Absolutely do not change names of medicine.

Prescription in question:
\'\'\'
{}
\'\'\'
'''.format(lines)


class Word:
    class Dot:
        def __init__(self, x, y):
            self.x = x
            self.y = y


    @staticmethod
    def get_center(box: list):
        return ((box[0] + box[2] + box[4] + box[6])/4, (box[1] + box[3] + box[5] + box[7])/4)

    def __init__(self, boundingBox: list, text: str):
        self.up_left = self.Dot(boundingBox[0], boundingBox[1])
        self.up_right = self.Dot(boundingBox[2], boundingBox[3])
        self.down_right = self.Dot(boundingBox[4], boundingBox[5])
        self.down_left = self.Dot(boundingBox[6], boundingBox[7])
        self.text: str = text
        self.center = self.Dot(*self.get_center(boundingBox))

        self.upmost: int = min(self.up_left.y, self.up_right.y)
        self.downmost: int = max(self.down_left.y, self.down_right.y)
        self.height = self.downmost - self.upmost

    def __str__(self):
        return self.text


class CurrentCenter:
    def __init__(self, dot: Word.Dot, height: int):
        self.center_count = 1
        self.current_center = Word.Dot(dot.x, dot.y)
        self.height = float(height)
        self.upper = self.current_center.y - self.height/2
        self.lower = self.current_center.y + self.height/2

    def append(self, dot: Word.Dot, height: int):
        self.center_count += 1
        self.current_center = Word.Dot((self.current_center.x * (self.center_count - 1) + dot.x) / self.center_count, (self.current_center.y * (self.center_count - 1) + dot.y) / self.center_count)
        self.height = (self.height * (self.center_count - 1) + height) / self.center_count
        self.upper = self.current_center.y - self.height/2
        self.lower = self.current_center.y + self.height/2
