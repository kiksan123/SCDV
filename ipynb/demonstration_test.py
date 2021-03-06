
# coding: utf-8

# In[ ]:


import time
import warnings
from gensim.models import Word2Vec
import pandas as pd
import time
from nltk.corpus import stopwords
import numpy as np
import sys
import os
sys.path.append("../20news")
from KaggleWord2VecUtility import KaggleWord2VecUtility
from numpy import float32
import math
from sklearn.ensemble import RandomForestClassifier
from sklearn.externals import joblib
from sklearn.feature_extraction.text import TfidfVectorizer,HashingVectorizer
from sklearn.svm import SVC, LinearSVC
import pickle
from math import *
from sklearn.metrics import classification_report
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import GridSearchCV
from sklearn.preprocessing import label_binarize


# In[ ]:


num_features = 200     # Word vector dimensionality
min_word_count = 20   # Minimum word count
num_workers = 40       # Number of threads to run in parallel
context = 10          # Context window size
downsampling = 1e-3   # Downsample setting for frequent words


# In[ ]:


model_name = str(num_features) + "features_" + str(min_word_count) + "minwords_" + str(context) + "context_len2alldata"
# Load the trained Word2Vec model.
model = Word2Vec.load(os.path.join("../20news/",model_name))
# Get wordvectors for all words in vocabulary.
word_vectors = model.wv.syn0


# In[ ]:


def cluster_GMM(num_clusters, word_vectors):
	# Initalize a GMM object and use it for clustering.
    clf =  GaussianMixture(n_components=num_clusters,
                    covariance_type="tied", init_params='kmeans', max_iter=50)
	# Get cluster assignments.
    clf.fit(word_vectors)
    idx = clf.predict(word_vectors)
    print ("Clustering Done...")
	# Get probabilities of cluster assignments.
    idx_proba = clf.predict_proba(word_vectors)
# 	# Dump cluster assignments and probability of cluster assignments. 
# 	joblib.dump(idx, 'gmm_latestclusmodel_len2alldata.pkl')
# 	print ("Cluster Assignments Saved...")

# 	joblib.dump(idx_proba, 'gmm_prob_latestclusmodel_len2alldata.pkl')
# 	print ("Probabilities of Cluster Assignments Saved...")
    return idx, idx_proba

def read_GMM(idx_name, idx_proba_name):
	# Loads cluster assignments and probability of cluster assignments. 
	idx = joblib.load(idx_name)
	idx_proba = joblib.load(idx_proba_name)
	print ("Cluster Model Loaded...")
	return (idx, idx_proba)


# In[ ]:


# Set number of clusters.
num_clusters = 60
# Uncomment below line for creating new clusters.
idx, idx_proba = cluster_GMM(num_clusters, word_vectors)


# In[ ]:


# Create a Word / Index dictionary, mapping each vocabulary word to
# a cluster number
word_centroid_map = dict(zip( model.wv.index2word, idx ))
# Create a Word / Probability of cluster assignment dictionary, mapping each vocabulary word to
# list of probabilities of cluster assignments.
word_centroid_prob_map = dict(zip( model.wv.index2word, idx_proba ))


# In[ ]:


# Load train data.
train = pd.read_csv( '../20news/data/train_v2.tsv', header=0, delimiter="\t")
# Load test data.
test = pd.read_csv( '../20news/data/test_v2.tsv', header=0, delimiter="\t")
all = pd.read_csv( '../20news/data/all_v2.tsv', header=0, delimiter="\t")


# In[ ]:


# Computing tf-idf values.
traindata = []
for i in range(len(all["news"])):
    traindata.append(" ".join(KaggleWord2VecUtility.review_to_wordlist(all["news"][i], True)))

tfv = TfidfVectorizer(strip_accents='unicode',dtype=np.float32)
tfidfmatrix_traindata = tfv.fit_transform(traindata)
featurenames = tfv.get_feature_names()
idf = tfv._tfidf.idf_


# In[ ]:


# Creating a dictionary with word mapped to its idf value 
print ("Creating word-idf dictionary for Training set...")

word_idf_dict = {}
for pair in zip(featurenames, idf):
    word_idf_dict[pair[0]] = pair[1]


# In[ ]:


word_idf_dict


# In[ ]:


def get_probability_word_vectors(featurenames, word_centroid_map, num_clusters, word_idf_dict):
	# This function computes probability word-cluster vectors.
	prob_wordvecs = {}
	for word in word_centroid_map:
		prob_wordvecs[word] = np.zeros( num_clusters * num_features, dtype="float32" )
		for index in range(0, num_clusters):
			try:
				prob_wordvecs[word][index*num_features:(index+1)*num_features] = model[word] * word_centroid_prob_map[word][index] * word_idf_dict[word]
			except:
				continue

	# prob_wordvecs_idf_len2alldata = {}
	# i = 0
	# for word in featurenames:
	# 	i += 1
	# 	if word in word_centroid_map:	
	# 		prob_wordvecs_idf_len2alldata[word] = {}
	# 		for index in range(0, num_clusters):
	# 				prob_wordvecs_idf_len2alldata[word][index] = model[word] * word_centroid_prob_map[word][index] * word_idf_dict[word] 

	

	# for word in prob_wordvecs_idf_len2alldata.keys():
	# 	prob_wordvecs[word] = prob_wordvecs_idf_len2alldata[word][0]
	# 	for index in prob_wordvecs_idf_len2alldata[word].keys():
	# 		if index==0:
	# 			continue
	# 		prob_wordvecs[word] = np.concatenate((prob_wordvecs[word], prob_wordvecs_idf_len2alldata[word][index]))
	return prob_wordvecs


# In[ ]:


# Pre-computing probability word-cluster vectors.
prob_wordvecs = get_probability_word_vectors(featurenames, word_centroid_map, num_clusters, word_idf_dict)


# In[ ]:


gwbowv = np.zeros( (train["news"].size, num_clusters*(num_features)), dtype="float32")


# In[ ]:


def create_cluster_vector_and_gwbowv(prob_wordvecs, wordlist, word_centroid_map, word_centroid_prob_map, dimension, word_idf_dict, featurenames, num_centroids, train=False):
	# This function computes SDV feature vectors.
    # num_clusters = num_centroids
    # num_features = dimension
	bag_of_centroids = np.zeros( num_centroids * dimension, dtype="float32" )
	global min_no
	global max_no

	for word in wordlist:
		try:
            # return cluster
			temp = word_centroid_map[word]
		except:
			continue
        
        # plus probability
		bag_of_centroids += prob_wordvecs[word]

	norm = np.sqrt(np.einsum('...i,...i', bag_of_centroids, bag_of_centroids))
	if(norm!=0):
		bag_of_centroids /= norm

	# To make feature vector sparse, make note of minimum and maximum values.
	if train:
		min_no += min(bag_of_centroids)
		max_no += max(bag_of_centroids)

	return bag_of_centroids


# In[ ]:


counter = 0
min_no = 0
max_no = 0
for review in train["news"]:
    # Get the wordlist in each news article.
    # Create each Document vector
    words = KaggleWord2VecUtility.review_to_wordlist( review,remove_stopwords=True )
    gwbowv[counter] = create_cluster_vector_and_gwbowv(prob_wordvecs, words, word_centroid_map, word_centroid_prob_map, num_features, word_idf_dict, featurenames, num_clusters, train=True)
    counter+=1
    if counter % 1000 == 0:
        print ("Train News Covered : ",counter)


# In[ ]:


counter = 0
gwbowv_test = np.zeros( (test["news"].size, num_clusters*(num_features)), dtype="float32")
for review in test["news"]:
    # Get the wordlist in each news article.
    words = KaggleWord2VecUtility.review_to_wordlist( review,         remove_stopwords=True )
    gwbowv_test[counter] = create_cluster_vector_and_gwbowv(prob_wordvecs, words, word_centroid_map, word_centroid_prob_map, num_features, word_idf_dict, featurenames, num_clusters)
    counter+=1
    if counter % 1000 == 0:
        print ("Test News Covered : ",counter)


# In[ ]:


print ("Making sparse...")
# Set the threshold percentage for making it sparse. 
percentage = 0.04
min_no = min_no*1.0/len(train["news"])
max_no = max_no*1.0/len(train["news"])
print ("Average min: ", min_no)
print ("Average max: ", max_no)
thres = (abs(max_no) + abs(min_no))/2
thres = thres*percentage

# Make values of matrices which are less than threshold to zero.
temp = abs(gwbowv) < thres
gwbowv[temp] = 0

temp = abs(gwbowv_test) < thres
gwbowv_test[temp] = 0

