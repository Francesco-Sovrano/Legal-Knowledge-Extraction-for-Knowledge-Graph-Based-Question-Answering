import os
# os.environ["CUDA_VISIBLE_DEVICES"]="-1"
import multiprocessing
import types
import spacy # for natural language processing
# import neuralcoref # for Coreference Resolution
# python3 -m spacy download en_core_web_md
from sklearn.preprocessing import normalize
import numpy as np
import tensorflow as tf
# import tensorflow.compat.v1 as tf
# tf.disable_v2_behavior() # use 1.X API
tf.get_logger().setLevel('ERROR') # Reduce logging output.
gpu_devices = tf.config.experimental.list_physical_devices('GPU')
for dev in gpu_devices:
	tf.config.experimental.set_memory_growth(dev, True)
import tensorflow_hub as hub
import tensorflow_text
from pathlib import Path
from transformers import AutoConfig, AutoTokenizer, AutoModelWithLMHead, pipeline
import torch

from misc.doc_reader import load_or_create_cache, create_cache, load_cache

import warnings
warnings.filterwarnings('ignore')

def get_best_gpu():
	if torch.cuda.device_count() == 0:
		return -1
	return min(
		(
			(i,torch.cuda.memory_allocated(i))
			for i in range(torch.cuda.device_count())
		),
		key = lambda x:x[-1]
	)[0]

is_listable = lambda x: type(x) in (list,tuple)

class ModelManager():
	# static members
	__nlp_models = {}
	__tf_embedders = {}
	__hf_embedders = {}

	def __init__(self, model_options=None):
		if not model_options:
			model_options = {}
		self.model_options = model_options
		self.disable_spacy_component = []
		self.__batch_size = model_options.get('batch_size', 100)

		self.__spacy_cache = {}
		self.__tf_cache = {}
		self.__hf_cache = {}

		self.__spacy_model = model_options.get('spacy_model', 'en_core_web_md')
		self.__tf_model = model_options.get('tf_model', {})
		self.__hf_model = model_options.get('hf_model', {})

	def store_cache(self, cache_name):
		cache_dict = {
			'tf_cache': self.__tf_cache,
			'spacy_cache': self.__spacy_cache,
			'hf_cache': self.__hf_cache,
		}
		create_cache(cache_name, lambda: cache_dict)

	def load_cache(self, cache_name):
		loaded_cache = load_cache(cache_name)
		if loaded_cache:

			tf_cache = loaded_cache.get('tf_cache',None)
			if tf_cache:
				self.__tf_cache = tf_cache

			hf_cache = loaded_cache.get('hf_cache',None)
			if hf_cache:
				self.__hf_cache = hf_cache

			spacy_cache = loaded_cache.get('spacy_cache',None)
			if spacy_cache:
				self.__spacy_cache = spacy_cache

	@staticmethod
	def get_cached_values(value_list, cache, fetch_fn, key_fn=lambda x:x):
		missing_values = [q for q in value_list if key_fn(q) not in cache]
		if len(missing_values) > 0:
			new_values = fetch_fn(missing_values)
			cache.update({key_fn(q):v for q,v in zip(missing_values, new_values)})
		return [cache[key_fn(q)] for q in value_list]

	@staticmethod
	def load_nlp_model(spacy_model):
		print('## Loading Spacy model <{}>...'.format(spacy_model))
		# go here <https://spacy.io/usage/processing-pipelines> for more information about Language Processing Pipeline (tokenizer, tagger, parser, etc..)
		nlp = spacy.load(spacy_model)
		# nlp.add_pipe(nlp.create_pipe("merge_noun_chunks"))
		# nlp.add_pipe(nlp.create_pipe("merge_entities"))
		# nlp.add_pipe(nlp.create_pipe("merge_subtokens"))
		#################################
		# nlp.add_pipe(neuralcoref.NeuralCoref(nlp.vocab), name='neuralcoref', last=True) # load NeuralCoref and add it to the pipe of SpaCy's model
		# def remove_unserializable_results(doc): # Workaround for serialising NeuralCoref's clusters
		# 	def cluster_as_doc(c):
		# 		c.main = c.main.as_doc()
		# 		c.mentions = [
		# 			m.as_doc()
		# 			for m in c.mentions
		# 		]
		# 	# doc.user_data = {}
		# 	if not getattr(doc,'_',None):
		# 		return doc
		# 	if not getattr(doc._,'coref_clusters',None):
		# 		return doc
		# 	for cluster in doc._.coref_clusters:
		# 		cluster_as_doc(cluster)
		# 	for token in doc:
		# 		for cluster in token._.coref_clusters:
		# 			cluster_as_doc(cluster)
		# 	return doc
		# nlp.add_pipe(remove_unserializable_results, last=True)
		print('## Spacy model loaded')
		return nlp
	
	@staticmethod
	def load_tf_model(tf_model):
		cache_dir = tf_model.get('cache_dir',None)
		if cache_dir:
			Path(cache_dir).mkdir(parents=True, exist_ok=True)
			os.environ["TFHUB_CACHE_DIR"] = cache_dir

		model_url = tf_model['url']
		is_qa_model = 'qa' in model_url.lower()
		if is_qa_model:
			print(f'## Loading TF model <{model_url}> for QA...')
		else:
			print(f'## Loading TF model <{model_url}>...')
		module = hub.load(model_url)
		get_input = lambda y: tf.constant(tuple(map(lambda x: x[0] if is_listable(x) else x, y)))
		if is_qa_model:
			get_context = lambda y: tf.constant(tuple(map(lambda x: x[1] if is_listable(x) else '', y)))
			q_label = "query_encoder" if 'query_encoder' in module.signatures else 'question_encoder'
			q_module = lambda doc: module.signatures[q_label](input=get_input(doc))['outputs'].numpy() # The default signature is identical with the question_encoder signature.
			a_module = lambda doc: module.signatures['response_encoder'](input=get_input(doc), context=get_context(doc))['outputs'].numpy()
		else:
			q_module = a_module = lambda doc: module(get_input(doc)).numpy()
		print('## TF model loaded')
		return {
			'question': q_module,
			'answer': a_module
		}

	@staticmethod
	def load_hf_model(hf_model):
		model_name = hf_model['url']
		model_type = hf_model['type']
		model_framework = hf_model.get('framework', 'pt')
		cache_dir = hf_model.get('cache_dir',None)
		if cache_dir:
			model_path = os.path.join(cache_dir, model_name.replace('/','-'))
			if not os.path.isdir(model_path):
				os.mkdir(model_path)
		else:
			model_path = None
		print(f'###### Loading {model_type} model <{model_name}> for {model_framework} ######')
		config = AutoConfig.from_pretrained(model_name, cache_dir=model_path) # Download configuration from S3 and cache.
		model = AutoModelWithLMHead.from_pretrained(model_name, cache_dir=model_path)
		tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=model_path)
		print(f'###### <{model_name}> loaded ######')
		return {
			'pipeline': pipeline(model_type, model=model, tokenizer=tokenizer, framework=model_framework, device=get_best_gpu()),
			'tokenizer': tokenizer,
			'model': model,
			'config': config,
		}
	
	def get_nlp_model(self):
		if ModelManager.__nlp_models.get(self.__spacy_model, None) is None:
			ModelManager.__nlp_models[self.__spacy_model] = ModelManager.load_nlp_model(self.__spacy_model)
		return ModelManager.__nlp_models[self.__spacy_model]

	def get_tf_model(self):
		model_key = self.__tf_model['url']
		if ModelManager.__tf_embedders.get(model_key, None) is None:
			ModelManager.__tf_embedders[model_key] = ModelManager.load_tf_model(self.__tf_model)
		return ModelManager.__tf_embedders[model_key]

	def get_hf_model(self):
		model_key = (self.__hf_model['url'],self.__hf_model['type'])
		if ModelManager.__hf_embedders.get(model_key, None) is None:
			ModelManager.__hf_embedders[model_key] = ModelManager.load_hf_model(self.__hf_model)
		return ModelManager.__hf_embedders[model_key]

	def nlp(self, text_list, disable=None, n_threads=None, batch_size=None):
		if not disable:
			disable = self.disable_spacy_component
		if not n_threads: # real multi-processing: https://git.readerbench.com/eit/prepdoc/blob/f8e93b6d0a346e9a53dac2e70e5f1712d40d6e1e/examples/parallel_parse.py
			n_threads = multiprocessing.cpu_count()
		if not batch_size:
			batch_size = self.__batch_size
		def fetch_fn(missing_text):
			return self.get_nlp_model().pipe(
				missing_text, 
				disable=disable, 
				batch_size=min(batch_size, int(np.ceil(len(missing_text)/n_threads))),
				n_process=min(n_threads, len(missing_text)), # The keyword argument n_threads on the .pipe methods is now deprecated, as the v2.x models cannot release the global interpreter lock. (Future versions may introduce a n_process argument for parallel inference via multiprocessing.) - https://spacy.io/usage/v2-1#incompat
			)
		return self.get_cached_values(text_list, self.__spacy_cache, fetch_fn)

	def run_tf_embedding(self, doc_list, norm=None, as_question=False):
		def fetch_fn(missing_queries):
			# print(missing_queries)
			tf_model = self.get_tf_model()
			# Feed missing_queries into current tf graph
			batch_list = (
				missing_queries[i*self.__batch_size:(i+1)*self.__batch_size] 
				for i in range(np.int(np.ceil(len(missing_queries)/self.__batch_size)))
			)
			encoder = tf_model['question' if as_question else 'answer']
			batched_embeddings = tuple(map(encoder, batch_list))
			embeddings = np.concatenate(batched_embeddings, 0)
			# Normalize the embeddings, if required
			if norm is not None:
				embeddings = normalize(embeddings, norm=norm)
			return embeddings
		return np.array(self.get_cached_values(doc_list, self.__tf_cache, fetch_fn, key_fn=lambda x:(x,as_question)))

	def run_hf_task(self, inputs, **kwargs):
		def fetch_fn(missing_inputs):
			hf_model = self.get_hf_model()
			return [hf_model['pipeline'](i, **kwargs) for i in missing_inputs]
		cache_key = '.'.join(map(lambda x: '='.join(map(str,x)), sorted(kwargs.items(), key=lambda x:x[0])))
		return self.get_cached_values(inputs, self.__hf_cache, fetch_fn, key_fn=lambda x: '.'.join((cache_key,x)))

	def get_similarity_vector(self, source_text_list, target_text_list, similarity_fn=np.inner, as_question=False):
		source_embedding = self.run_tf_embedding(doc_list=source_text_list, as_question=as_question)
		target_embeddings = self.run_tf_embedding(doc_list=target_text_list, as_question=False)
		return similarity_fn(source_embedding,target_embeddings)

	# np.inner == lambda x,y: np.matmul(x,np.transpose(y))
	def find_most_similar(self, source_text, target_text_list, similarity_fn=np.inner, as_question=False):
		similarity_vec = self.get_similarity_vector(
			source_text=source_text, 
			target_text_list=target_text_list, 
			similarity_fn=similarity_fn, 
			as_question=as_question,
		)
		argmax = np.argmax(similarity_vec)
		return argmax, similarity_vec[argmax]
	