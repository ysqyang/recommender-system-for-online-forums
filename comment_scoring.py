import networkx as nx
from gensim import corpora, models, similarities
import numpy as np

def text_vector(text, tokenize_fn):
    '''
    Converts Chinese text to a vector using word embeddings
    Args:
    text:        text to be converted
    tokenize_fn: function to tokenize a text
    '''
    words = tokenize_fn(text)
    v = np.zeros(64)      
    
    for word in words:
        v += model[word]
    
    return v/len(words)

def text_similarity(text_1, text_2, text_to_vector_fn, word2vec_model_path):
    '''
    Computes the similarity between two texts
    Args:
    text_1:              Chinese text tokenized into words
    text_2:              Chinese text tokenized into words
    text_to_vector_fn:   function to convert a text to a vector 
    word2vec_model_path: path of binary word2vec model file
    '''
    model = models.KeyedVectors.load_word2vec_format(
                                word2vec_model_path, binary=True)

    v1, v2 = text_to_vector_fn(text_1), text_to_vector_fn(text_2)

    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def make_similarity_graph(texts, similarity_fn):
    '''
    Creates a undirected graph with texts as nodes.
    An edge exists between two texts if and only they
    have a nonzero similarity score.
    Args:
    texts:         list of text id's for which pairwise similarities
                   are to be computed
    similarity_fn: function to compute the similarity between two texts
    '''

    G = nx.Graph()  # similarity is symmetric, so the graph is undirected
    G.add_nodes_from(texts)
    num_texts = len(texts)
    for i in range(num_texts):
        for j in range(i+1, num_texts):
            G.add_edge(texts[i], texts[j], 
                       weight=similarity_fn(texts[i], texts[j]))

    return G

def pagerank(G, alpha):
    '''
    Computes the PageRank of nodes in graph G
    Args:
    G:     graph for which the PageRank is to be computed
    alpha: damping coefficient in the PageRank algorithm
    '''
    return nx.pagerank(G, alpha=alpha)

def comment_importance(graphs, coefficients, alphas):
    '''
    Computes comment importance by linearly combining
    the PageRank for graphs in G 
    Args:
    graphs:       list of graphs
    coefficients: coefficients of the linear combination
    alphas:       damping factors used in the PageRank algorithm
    '''
    return sum([c*pagerank(g, a) for g, c, a in 
               zip(graphs, coefficients, alphas)])

'''
stopwords = get_stopwords('./stopwords.txt')

corpus = [tokenize(doc, stopwords) for doc in corpus]

dictionary = corpora.Dictionary(corpus)

for id_ in dictionary:
    print(id_, dictionary[id_])

corpus = [dictionary.doc2bow(text) for text in corpus]

print(corpus)

tfidf = models.TfidfModel(corpus)

converted = tfidf[corpus]
term_weights = {}
for doc in converted:
    max_weight = max([x[1] for x in doc])
    for word in doc:
        term_weights[word[0]] = term_weights.get(word[0], 0) + word[1]/max_weight

print(term_weights)

term_weights = {}
for doc in converted:
    max_weight = max([x[1] for x in doc])
    for word in doc:
        term_weights[dictionary[word[0]]] = term_weights.get(dictionary[word[0]], 0) + word[1]/max_weight

print(term_weights)


G = nx.Graph()
G.add_nodes_from([12423, 36781, 71842, 61359, 50127])
G.add_edge(12423, 71842, weight=10)
G.add_edge(61359, 50127, weight=5)
G.add_edge(71842, 36781, weight=4)
G.add_edge(12423, 61359, weight=2)
G.add_edge(36781, 50127, weight=7)

print(nx.pagerank(G))
'''












