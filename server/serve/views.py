from django.shortcuts import render
from django.http import JsonResponse
import json
import os
import sys
import logging
from datetime import datetime
import yaml
root_dir = os.path.dirname(sys.path[0])
config_path = os.path.abspath(os.path.join(root_dir, 'config'))
source_path = os.path.abspath(os.path.join(root_dir, 'source'))
sys.path.insert(0, config_path)
sys.path.insert(1, source_path)
import utils


# read configurations
while True:
    try:
        with open('config/config.yml', 'rb') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            break
    except Exception as e:
        logging.exception(e)

path_cfg = config['paths']
log_cfg = config['logging']
recom_cfg = config['recommendation']
misc_cfg = config['miscellaneous']

logger = utils.get_logger_with_config(name=log_cfg['serve_log_name'],
                                      logger_level=log_cfg['log_level'],
                                      handler_levels=log_cfg['handler_levels'],
                                      log_dir=log_cfg['dir'],
                                      mode=log_cfg['mode'],
                                      log_format=log_cfg['format'])


def serve_recommendations(request):
    '''
    Given the similarity matrix, generate top_num recommendations for
    target_tid
    '''
    if request.method == 'POST':
        return JsonResponse({'status': True,
                             'errorCode': 1,
                             'errorMessage': 'Method not allowed!',
                             'dto': {'list': []},
                             '_t': datetime.now().timestamp()})

    n_dirs = misc_cfg['num_topic_files_per_folder']
    dir = path_cfg['topic_save_dir']
    tid = str(request.GET['topicID'])
    file_name = os.path.join(dir, str(int(tid) // n_dirs), tid)
            
    try:
        with open(file_name, 'r') as f:
            data = json.load(f)

        recoms = data['sim_list'][:recom_cfg['max_shown']]
        return JsonResponse({'status': True,
                             'errorCode': 0,
                             'errorMessage': '',
                             'dto': {'list': recoms},
                             '_t': datetime.now().timestamp()}) 
    except:
        logger.exception('Data file unavailable or corrupted')
        return JsonResponse({'status': True,
                             'errorCode': 2,
                             'errorMessage': 'Data file unavailable or corrupted',
                             'dto': {'list': []},
                             '_t': datetime.now().timestamp()})
