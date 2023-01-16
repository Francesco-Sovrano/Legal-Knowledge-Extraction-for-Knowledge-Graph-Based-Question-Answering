#!/bin/bash

MY_DIR="`python -c "import os; print(os.path.realpath('$1'))"`"
cd $MY_DIR

# Run YAI server
cd yai
echo 'Setting up YAI server..'
python3 -m venv .env
source .env/bin/activate
pip install -U pip setuptools wheel twine
pip install -r requirements.txt
cd ..

# Run OKE Server
cd oke
echo 'Setting up OKE server..'
python3 -m venv .env
source .env/bin/activate
pip install -U pip setuptools wheel twine
# cd .env/lib
# git clone https://github.com/huggingface/neuralcoref.git
# cd neuralcoref
# pip install -r requirements.txt
# pip install -e .
# cd ..
# cd ../..
pip install -r requirements.txt
python3 -m spacy download en_core_web_md
# python3 -m spacy download en_core_web_sm
python3 -m nltk.downloader stopwords punkt averaged_perceptron_tagger framenet_v17 wordnet brown
cd ..
