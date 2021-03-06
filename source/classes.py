# class definitions
import re
import time
import os
import glob
import math
import json
from gensim import corpora, matutils
from gensim.models import tfidfmodel, LdaModel
#from gensim.similarities import Similarity
from gensim.models import Word2Vec
import numpy as np
import jieba
from utils import insert, remove

NUM_SECONDS_PER_DAY = 86400

class TextPreprocessor(object):
    def __init__(self, singles, puncs, punc_frac_low, punc_frac_high,
                 valid_count, valid_ratio, stopwords):
        self.singles = singles
        self.puncs = puncs
        self.punc_frac_low = punc_frac_low
        self.punc_frac_high = punc_frac_high
        self.valid_count = valid_count
        self.valid_ratio = valid_ratio
        self.stopwords = stopwords

    def preprocess(self, text):
        '''
        Tokenize a Chinese document to a list of words
        Args:
        text: text to be tokenized
        '''
        cnt = 0
        for c in text:
            if c in self.puncs:
                cnt += 1

        ratio = cnt / len(text)

        if ratio < self.punc_frac_low or ratio > self.punc_frac_high:
            return []

        alphanum, whitespace = r'\\*\w+', r'\s'
        word_list = []
        words = jieba.cut(text, cut_all=False)

        for word in words:
            if len(word) == 1 \
                    or re.match(alphanum, word, flags=re.ASCII) \
                    or re.match(whitespace, word, flags=re.ASCII) \
                    or word in self.stopwords \
                    or any(c in self.singles for c in word) \
                    or len(word) / len(set(word)) > 2:
                continue
            word_list.append(word)

        if len(word_list) < self.valid_count \
                or len(word_list) / len(set(word_list)) > self.valid_ratio: \
            return []

        return word_list


class AbstractCorpus(object):
    '''
    Corpus object
    '''
    def __init__(self, name, logger):
        self.data = {}
        self.dictionary = corpora.Dictionary([])
        self.name = name
        self.logger = logger

    @property
    def size(self):
        return len(self.data)

    @property
    def oldest(self):
        if len(self.data) == 0:
            return None
        return min(self.data.keys())

    @property
    def latest(self):
        if len(self.data) == 0:
            return None
        return max(self.data.keys())

    def add(self, topic_id, content, date):
        return NotImplemented

    def delete(self, topic_id):
        return NotImplemented

    def load(self, save_dir):
        return NotImplemented

    def save(self, save_dir, num_files_per_folder):
        return NotImplemented


class CorpusTfidf(AbstractCorpus):
    def __init__(self, name, target_corpus, tfidf_scheme, num_keywords,
                 time_decay, max_recoms, logger):
        super().__init__(name=name,
                         logger=logger)
        self.target_corpus = target_corpus
        self.tfidf_scheme = tfidf_scheme
        self.num_keywords = num_keywords
        self.time_decay = time_decay
        self.max_recoms = max_recoms

    def _update_keywords(self):
        """
        For each topic in the corpus, generate using TFIDF a list of
        n_keywords most importance keywords in the form of token-to-weight
        mapping
        :param n_keywords: number of keywords to store for each topic
        """
        corpus_bow = [self.dictionary.doc2bow(data['body'])
                      for data in self.data.values()]
        tfidf = tfidfmodel.TfidfModel(corpus_bow, smartirs=self.tfidf_scheme)

        for tid, data in self.data.items():
            weights = tfidf[self.dictionary.doc2bow(data['body'])]
            weights.sort(key=lambda x: x[1], reverse=True)
            # generate token-to-weight mapping instead of id-to-weight mapping
            data['keywords'] = {self.dictionary[wid]: weight
                                for wid, weight in weights[:self.num_keywords]}

    def add(self, topic_id, content, date):
        self.data[topic_id] = {'date': date,
                               'body': content,
                               'recommendations': [],
                               'updated': True
                               }

        self.dictionary.add_documents([content])
        self._generate_recommendations(topic_id, date)
        self.logger.info('Special topic %s added to %s (%d)', topic_id, self.name, len(self.data))

    def _generate_recommendations(self, topic_id, date):
        self._update_keywords()
        for tid, data in self.target_corpus.data.items():
            relevance = sum(self.data[topic_id]['keywords'].get(word, 0) for word in data['body'])
            day_delta = (int(date) - int(data['date'])) / NUM_SECONDS_PER_DAY
            relevance *= min(1.0, math.pow(self.time_decay, day_delta))
            del_id = insert(self.data[topic_id]['recommendations'], tid, relevance, self.max_recoms)
            if del_id is None:
                continue
            data['appears_in_special'].append(topic_id)
            if del_id != '':
                remove(data['appears_in_special'], del_id)

    def update_on_new_topic(self, topic_id, content, date):
        """
        updates recommendation data for special topics
        """
        if len(content) == 0:
            return

        for tid, data in self.data.items():
            relevance = sum(data['keywords'].get(word, 0) for word in content)
            day_delta = (int(data['date']) - int(date)) / NUM_SECONDS_PER_DAY  # convert to number of days
            relevance *= min(1.0, math.pow(self.time_decay, day_delta))
            del_id = insert(data['recommendations'], topic_id, relevance, self.max_recoms)
            if del_id is None:  # no insertion performed
                continue
            self.data[tid]['updated'] = True
            self.target_corpus.data[topic_id]['appears_in_special'].append(tid)
            if del_id != '':
                remove(self.target_corpus.data[del_id]['appears_in_special'], tid)

    def update_on_delete_topic(self, topic_id):
        if topic_id not in self.target_corpus.data:
            return

        for tid in self.target_corpus.data[topic_id]['appears_in_special']:
            if topic_id in self.data[tid]['recommendations']:
                remove(self.data[tid]['recommendations'], topic_id)

    def delete(self, topic_id):
        if topic_id not in self.data:
            return

        for tid in self.data[topic_id]['recommendations']:
            remove(self.target_corpus.data[tid]['appears_in_special'], topic_id)

        del self.data[topic_id]

        self.logger.info('Topic %s deleted', topic_id)

    def load(self, save_dir):
        for file in glob.glob(os.path.join(save_dir, '[0-9]*')):
            try:
                with open(file, 'r') as f:
                    rec = json.load(f)
                    self.data[file] = {'date': rec['date'],
                                       'body': rec['body'],
                                       'keywords': rec['keywords'],
                                       'recommendations': rec['recommendations'],
                                       'updated': False
                                       }
            except json.JSONDecodeError:
                self.logger.error('Failed to load special topic %s', file)

        self.logger.info('%d special topics loaded from disk', len(self.data))

        if len(self.data) > 0:
            corpus = [data['body'] for data in self.data.values()]
            self.dictionary = corpora.Dictionary(corpus)

    def save(self, save_dir, num_files_per_folder=None):
        '''
        Saves the corpus and similarity data to disk
        Args:
        save_dir: directory under which to save the data
        num_files_per_folder: maximum number of saved topic files per folder
        '''
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        for tid, data in self.data.items():
            if data['updated']:
                record = {'date': data['date'],
                          'body': data['body'],
                          'keywords': data['keywords'],
                          'recommendations': data['recommendations']}
                with open(os.path.join(save_dir, tid), 'w') as f:
                    json.dump(record, f)
                self.logger.info('Special topic %s saved on disk', tid)
            else:
                self.logger.info('No updates for topic %s', tid)


class CorpusSimilarity(AbstractCorpus):
    '''
    Corpus collection
    '''
    def __init__(self, name, time_decay, duplicate_thresh,
                 irrelevant_thresh, max_recoms, logger):
        super().__init__(name=name,
                         logger=logger)
        self.time_decay = time_decay
        self.duplicate_thresh = duplicate_thresh
        self.irrelevant_thresh = irrelevant_thresh
        self.max_recoms = max_recoms

    def _update_pairwise_similarity(self, topic_id, content, date):
        """
        updates similarity data within the corpus
        """
        bow = self.dictionary.doc2bow(content)
        for tid, data in self.data.items():
            day_delta = (int(date) - int(data['date'])) / NUM_SECONDS_PER_DAY
            time_factor = math.pow(self.time_decay, day_delta)
            if tid == topic_id:
                continue
            bow1 = self.dictionary.doc2bow(data['body'])
            sim = matutils.cossim(bow, bow1)
            sim_1 = sim * min(1.0, 1/time_factor)
            sim_2 = sim * min(1.0, time_factor)

            if self.irrelevant_thresh <= sim_1 <= self.duplicate_thresh:
                del_id = insert(data['sim_list'], topic_id, sim_1, self.max_recoms)
                if del_id is not None:
                    self.data[topic_id]['appears_in'].append(tid)
                    self.data[tid]['updated'] = True
                    if del_id != '':
                        remove(self.data[del_id]['appears_in'], tid)

            if self.irrelevant_thresh <= sim_2 <= self.duplicate_thresh:
                del_id = insert(self.data[topic_id]['sim_list'], tid, sim_2, self.max_recoms)
                if del_id is not None:
                    self.data[tid]['appears_in'].append(topic_id)
                    if del_id != '':
                        remove(self.data[del_id]['appears_in'], topic_id)

    def add(self, topic_id, content, date):
        if len(content) == 0:
            self.logger.info('Topic %s is not recommendable', topic_id)
            return

        self.dictionary.add_documents([content])

        self.data[topic_id] = {'date': date,
                               'body': content,
                               'sim_list': [],
                               'appears_in': [],
                               'appears_in_special': [],
                               'updated': True}

        self._update_pairwise_similarity(topic_id, content, date)

        self.logger.info('Topic %s added to %s (%d)', topic_id, self.name, len(self.data))

    def delete(self, topic_id):
        if topic_id not in self.data:
            return

        for tid in self.data[topic_id]['appears_in']:  # list of topic id's whose similarity lists tid appears in
            if tid in self.data:
                remove(self.data[tid]['sim_list'], topic_id)
                self.data[tid]['updated'] = True

        del self.data[topic_id]
        self.logger.info('Topic %s deleted (%d)', topic_id, len(self.data))

    def remove_before(self, t):
        for tid in list(self.data.keys()):
            if self.data[tid]['date'] < t:
                self.delete(tid)

    def find_most_similar(self, topic):
        """
        Given a topic, compute its similarities with all topics 
        in the corpus and return the top n most similar ones from 
        the corpus
        """
        sim_list = []
        bow = self.dictionary.doc2bow(topic['body'])

        for tid, data in self.data.items():
            bow1 = self.dictionary.doc2bow(data['body'])
            sim = matutils.cossim(bow, bow1)
            if self.irrelevant_thresh <= sim <= self.duplicate_thresh:
                insert(sim_list, tid, sim, self.max_recoms)

        return sim_list

    def load(self, save_dir):
        for file in glob.glob(os.path.join(save_dir, '[0-9]*', '[0-9]*')):
            try:
                with open(file, 'r') as f:
                    rec = json.load(f)
                    self.data[file] = {'date': rec['date'],
                                       'body': rec['body'],
                                       'sim_list': rec['sim_list'],
                                       'appears_in': rec['appears_in'],
                                       'appears_in_special': rec['appears_in_special'],
                                       'updated': False
                                       }
            except json.JSONDecodeError:
                self.logger.error('Failed to load topic %s', file)
            except KeyError:
                self.logger.error('Vital keys missing in topic file %s', file)

        self.logger.info('%d topics loaded from disk', len(self.data))

        if len(self.data) > 0:
            corpus = [data['body'] for data in self.data.values()]
            self.dictionary = corpora.Dictionary(corpus)

    def save(self, save_dir, num_files_per_folder):
        '''
        Saves the corpus and similarity data to disk
        Args:
        save_dir: directory under which to save the data
        num_files_per_folder: maximum number of saved topic files per folder
        ''' 
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        for tid, data in self.data.items():
            if data['updated']:
                record = {'date': data['date'],
                          'body': data['body'],
                          'sim_list': data['sim_list'],
                          'appears_in': data['appears_in'],
                          'appears_in_special': data['appears_in_special']}
                path = os.path.join(save_dir, str(int(tid)//num_files_per_folder))
                # build the subdir for storing topics
                if not os.path.exists(path):
                    os.makedirs(path)
                filename = os.path.join(path, tid)
                with open(filename, 'w') as f:
                    json.dump(record, f)
                data['updated'] = False
                self.logger.info('Data for topic %s updated on disk', tid)
            else:
                self.logger.info('No updates for topic %s', tid)


class CorpusInference(AbstractCorpus):
    def __init__(self, name, target_corpus, logger, num_topics):
        super().__init__(name=name, logger=logger)
        self.target_corpus = target_corpus
        self.num_topics = num_topics
        self.lda = None

    def add(self, topic_id, content, date):
        self.dictionary.add_documents([content])
        self.data[topic_id] = {'date': date,
                               'body': content,
                               'updated': False}

        self.lda.update([content])
        self.logger.info('Topic %s added to %s (%d)', topic_id, self.name, len(self.data))

    def delete(self, topic_id):
        del self.data[topic_id]

        self.logger.info('Topic %s deleted (%d)', topic_id, len(self.data))

    def load(self, save_dir):
        pass

    def save(self, save_dir, num_files_per_folder):
        pass
