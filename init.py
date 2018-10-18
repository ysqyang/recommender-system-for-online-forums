import utils
import topic_profiling as tp
import similarity as sim
import argparse
import constants as const
import topics
import database

def main(args):
    '''
    db = utils.get_database(_DB_INFO)
    if os.path.exists(const._TOPIC_ID_TO_TABLE_NUM):
        with open(const._TOPIC_ID_TO_TABLE_NUM, 'rb') as f:
            existing = pickle.load(f).keys() 
        new_topics = get_new_topics(db, existing)
        tid_to_table = utils.update_tid_to_table_num_mapping(
                             const._TOPIC_ID_TO_TABLE_NUM, db, new_topics)
    else:
        tid_to_table = utils.create_topic_id_to_table_num(
                             db, const._TOPIC_ID_TO_TABLE_NUM)
    
    if os.path.exists(const._TOPIC_ID_TO_REPLY_TABLE_NUM):
        tid_to_reply_table = utils.update_tid_to_reply_table_num_mapping(
                                   const._TOPIC_ID_TO_REPLY_TABLE_NUM, db, new_topics)
    else:
        tid_to_reply_table = utils.create_topic_id_to_reply_table(
                                   db, tid_to_table.keys(), const._TOPIC_ID_TO_REPLY_TABLE_NUM)

    if os.path.exists(const._TOPIC_ID_TO_DATE):
        tid_to_date = utils.update_tid_to_date_mapping(
                            const._TOPIC_ID_TO_DATE, db, new_topics, tid_to_table)
    else:
        tid_to_date = utils.create_topic_id_to_date(db, const._TOPIC_ID_TO_DATE)
    
    
    db = utils.get_database(const._DB_INFO)
    tid_to_table = utils.load_mapping(const._TOPIC_ID_TO_TABLE_NUM)
    
    tid_to_date = utils.load_mapping(const._TOPIC_ID_TO_DATE)
    '''
    stopwords = utils.load_stopwords(const._STOPWORDS)
    db = database.Database(*const._DB_INFO)
    topic_ids = utils.load_topics(db, const._TOPIC_FEATURES, const._DAYS, 
                                  const._TOPIC_FILE)

    topic_ids = utils.filter_topics(topic_ids, const._TOPIC_FILE, const._REPLY_FILE, 
                                    const._MIN_LEN, const._MIN_REPLIES, 
                                    const._MIN_REPLIES_1)

    
    utils.load_replies(db, topic_ids, const._REPLY_FEATURES, const._REPLY_FILE)
    word_weights = tp.compute_profiles(topic_ids=topic_ids,  
                                       features=const._REPLY_FEATURES, 
                                       weights=const._WEIGHTS, 
                                       preprocess_fn=utils.preprocess, 
                                       stopwords=stopwords, 
                                       update=False, 
                                       path=const._PROFILES, 
                                       alpha=args.alpha, 
                                       smartirs=args.smartirs)

    # get k most representative words for each topic
    profile_words = tp.get_profile_words(topic_ids=topic_ids, 
                                         profiles=word_weights,
                                         k=args.k, 
                                         update=False, 
                                         path=const._PROFILE_WORDS)
  
    similarities = sim.compute_similarities(corpus_topic_ids=topic_ids, 
                                            active_topic_ids=topic_ids,
                                            preprocess_fn=utils.preprocess, 
                                            stopwords=stopwords, 
                                            profile_words=profile_words, 
                                            coeff=args.beta,
                                            T=const._T,
                                            update=False, 
                                            path=const._SIMILARITIES)

    
if __name__ == '__main__': 
    parser = argparse.ArgumentParser()
    parser.add_argument('--alpha', type=float, default=0.7, 
                        help='''contribution coefficient for topic content 
                                in computing word weights''')
    parser.add_argument('--k', type=int, default=10, 
                        help='number of words to represent a discussion thread')
    parser.add_argument('--beta', type=float, default=0.5,
                        help='''contribution coefficient for in-document frequency
                                in computing word probabilities''')
    parser.add_argument('--smartirs', type=str, default='atn', help='type of tf-idf variants')

    args = parser.parse_args()
    main(args)
