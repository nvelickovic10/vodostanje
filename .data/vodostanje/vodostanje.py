#!/usr/bin/python
"""This script displays hydrological water level report"""

import sys
from sys import stdout
import re
import os
from os import listdir
from os.path import isfile, join
from base64 import b64encode
import urllib2
import math
import datetime
import time
import argparse
import pickle
import untangle
import requests
from django.utils.encoding import smart_str

reload(sys)
sys.setdefaultencoding('utf8')  # pylint: disable=E1101

API_URL = 'http://www.hidmet.gov.rs/latin/prognoza/prognoza_voda.xml'
STATION_IDS = {'BEZDAN': 42010, 'APATIN': 42015, 'BOGOJEVO': 42020, 'BACKA_PALANKA': 42030,
               'NOVI_SAD': 42035, 'ZEMUN': 42045, 'PANCEVO': 42050,
               'NOVI_KNEZEVAC': 44010, 'SENTA': 44020, 'TITEL': 44040,
               'SREMSKA_MITROVICA': 45090, 'SABAC': 45094, 'BEOGRAD': 45099,
               'VARVARIN': 47010, 'CUPRIJA': 47030, 'BAGRDAN': 47040, 'LJUBICEVSKI_MOST': 47090,
               'ALEKSINAC': 47570, 'JASIKA': 47195}
IMAGE_URLS = ['prl', 'ahl', 'tl', 'pl', 'nl']
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
# print CURRENT_DIR
HISTORY_SAVE_DIR = CURRENT_DIR + '/history/'
STATE_SAVE_FILE = CURRENT_DIR + '/state/last_state.pkl'
SEPARATOR = '========================================' + \
    '==========================================\n'

T_COLORS = {
    'NO_COLOR': '\033[0m',
    'DEFENCE': '\033[35m',
    'TITLE': '\033[0;34m',
    'INFO': '\033[32m',
    'WARNING': '\033[33m',
    'FAIL': '\033[31m',
    'PROGRESS': '\033[90m',
    'UNDERLINE': '\033[94m'
}

PROGRESS_BAR_SIZE = 40

HISTORY_FILES = [f for f in listdir(
    HISTORY_SAVE_DIR) if isfile(join(HISTORY_SAVE_DIR, f))]
HISTORY_FILES.sort()

# PARSE ARGS

PARSER = argparse.ArgumentParser(description='Vodostanje script')

PARSER.add_argument(
    'offset', help='history offset', nargs='?', type=int)

PARSER.add_argument(
    '-ls', '--list', help='list history', action='store_true')

PARSER.add_argument(
    '-a', '--all', help='show all data', action='store_true')

PARSER.add_argument(
    '-s', '--save', help='save current state', action='store_true')

PARSER.add_argument(
    '--restore', help='restore previous state', action='store_true')

PARSER.add_argument(
    '--report', help='display histogram', choices=STATION_IDS.keys(), nargs='?')

ARGS = PARSER.parse_args()

TIMESTAMP = time.time()
TIMESTAMP = datetime.datetime.fromtimestamp(TIMESTAMP).strftime('%Y%m%d')


def imgcat(data, width='auto', height='auto', preserveAspectRatio=False, inline=True, filename=''):
    '''
    The width and height are given as a number followed by a unit, or the word "auto".

        N: N character cells.
        Npx: N pixels.
        N%: N percent of the session's width or height.
        auto: The image's inherent size will be used to determine an appropriate dimension.
    '''

    buf = bytes()
    enc = 'utf-8'

    is_tmux = os.environ['TERM'].startswith('screen')

    # OSC
    buf += b'\033'
    if is_tmux:
        buf += b'Ptmux;\033\033'
    buf += b']'

    buf += b'1337;File='

    if filename:
        buf += b'name='
        buf += b64encode(filename.encode(enc))

    buf += b';size=%d' % len(data)
    buf += b';inline=%d' % int(inline)
    buf += b';width=%s' % width.encode(enc)
    buf += b';height=%s' % height.encode(enc)
    buf += b';preserveAspectRatio=%d' % int(preserveAspectRatio)
    buf += b':'
    buf += b64encode(data)

    # ST
    buf += b'\a'
    if is_tmux:
        buf += b'\033\\'

    buf += b'\n'

    stdout.write(buf)
    stdout.flush()


def show_histograms(station_id):
    """This function displays histogram"""
    for val in IMAGE_URLS:
        url = 'http://www.hidmet.gov.rs/podaci/izvestajne/' + \
            smart_str(val) + smart_str(station_id) + '.gif'

        if len(requests.get(url).content) > 43:
            # to_print = T_COLORS['UNDERLINE'] + T_COLORS['TITLE'] + \
            #  url + T_COLORS['NO_COLOR']
            # print to_print
            imgcat(requests.get(url).content)
            # print '\n'


def chunk_report(bytes_so_far, total_size):
    """This function reports downloaded data percentage"""
    percent = float(bytes_so_far) / total_size
    prc = math.trunc(PROGRESS_BAR_SIZE * percent)
    percent_bar = ''
    for k in range(0, PROGRESS_BAR_SIZE):
        if k <= prc:
            percent_bar += '#'
        else:
            percent_bar += '_'
    percent = round(percent * 100, 2)
    sys.stdout.write(T_COLORS['PROGRESS'] + percent_bar + T_COLORS['NO_COLOR'] +
                     " (%0.2f%%) Downloaded %d of %d bytes\r" %
                     (percent, bytes_so_far, total_size))

    if bytes_so_far >= total_size:
        sys.stdout.write('\n')


def chunk_read(response, chunk_size=64, report_hook=None):
    """This function downloads data chunk by chunk"""
    total_size = response.info().getheader('Content-Length').strip()
    total_size = int(total_size)
    bytes_so_far = 0
    return_data = ''

    while 1:
        chunk = response.read(chunk_size)
        bytes_so_far += len(chunk)
        # time.sleep (5.0 / 1000.0);
        if not chunk:
            break

        return_data += chunk
        if report_hook:
            report_hook(bytes_so_far, total_size)

    return return_data


def save_data(file_path, data):
    """This function saves data to disk"""
    with open(file_path, 'w') as data_file:
        data_file.write(smart_str(data).encode('utf8'))


def read_data(file_path):
    """This function reads data from disk"""
    with open(file_path) as data_file:
        return data_file


def save_obj(file_path, obj):
    """This function saves object to disk"""
    with open(file_path, 'wb') as data_file:
        pickle.dump(obj, data_file, pickle.HIGHEST_PROTOCOL)


def load_obj(file_path):
    """This function reads object from disk"""
    with open(file_path, 'rb') as data_file:
        return pickle.load(data_file)

def confirm_prompt(question):
    """This function displays confirmation prompt"""
    yes_vals = set(['yes', 'y', 'ye'])
    no_vals = set(['no', 'n', ''])
    option = None
    while option is None:
        sys.stdout.write(T_COLORS['WARNING'] + question + ' (n): ' + T_COLORS['NO_COLOR'])
        choice = raw_input().lower()
        if choice in yes_vals:
            option = True
        elif choice in no_vals:
            option = False
        else:
            sys.stdout.write(T_COLORS['FAIL'] + 'Please respond with \'yes\' or \'no\'!\n' + \
                T_COLORS['NO_COLOR'])
    return option

# CHECK IF LIST HISTORY_FILES
if ARGS.list:
    START_INDEX = len(HISTORY_FILES) - 10
    if START_INDEX < 0:
        START_INDEX = 0
    # print HISTORY_FILES
    TMP = "\n".join(smart_str(x[:-4][10:] + T_COLORS['WARNING'] + \
        ' (' + smart_str(len(HISTORY_FILES) - i - 1) + ')' + T_COLORS['NO_COLOR']) for i, x in
                    enumerate(HISTORY_FILES[START_INDEX:len(HISTORY_FILES)]))
    TO_PRINT = T_COLORS['INFO'] + 'HISTORY FILES (' + smart_str(len(HISTORY_FILES)) + '):' + \
        T_COLORS['NO_COLOR'] + '\n' + TMP + T_COLORS['NO_COLOR']
    print TO_PRINT
    exit(0)

# CHECK IF REPORT

if ARGS.report:
    show_histograms(STATION_IDS[ARGS.report])
    exit(0)

# CHECK IF RESTORE

if ARGS.restore:
    if confirm_prompt('ARE YOU SURE?'):
        if os.path.isfile(STATE_SAVE_FILE + '.bup'):
            os.rename(STATE_SAVE_FILE + '.bup', STATE_SAVE_FILE)
        TO_PRINT = T_COLORS['WARNING'] + \
            'STATE RESTORED' + \
            T_COLORS['NO_COLOR']
        print TO_PRINT
    else:
        TO_PRINT = T_COLORS['INFO'] + \
            'RESTORE CANCELED BY USER' + \
            T_COLORS['NO_COLOR']
        print TO_PRINT
    exit(0)

# CHECK IF SAVE AND OFFSET

if ARGS.save and ARGS.offset:
    TO_PRINT = T_COLORS['FAIL'] + \
        'OPTIONS [offset] AND --save ARE MUTUALLY EXCLUSIVE, COULD NOT SAVE STATE' + \
        T_COLORS['NO_COLOR']
    print TO_PRINT
    exit(357)

# GET DATA FROM API

if ARGS.offset:
    OFFSET = 1 + abs(ARGS.offset)
    if OFFSET > len(HISTORY_FILES):
        OFFSET = len(HISTORY_FILES)
    # print OFFSET
    FILE_PATH = HISTORY_SAVE_DIR + HISTORY_FILES[len(HISTORY_FILES) - OFFSET]
    TO_PRINT = T_COLORS['INFO'] + 'LOADING DATA FROM FILE ' + \
        T_COLORS['UNDERLINE'] + T_COLORS['TITLE'] + \
        FILE_PATH + T_COLORS['NO_COLOR']
    print TO_PRINT
    XML_DATA = untangle.parse(FILE_PATH)
    TO_PRINT = T_COLORS['INFO'] + 'DATA LOADED!!!' + \
        T_COLORS['UNDERLINE'] + T_COLORS['TITLE'] + ' (OFFSET: ' + \
        smart_str(OFFSET - 1) + ')' + T_COLORS['NO_COLOR']
    print TO_PRINT
else:
    TO_PRINT = T_COLORS['INFO'] + 'GETTING DATA FROM ' + \
        T_COLORS['UNDERLINE'] + T_COLORS['TITLE'] + \
        API_URL + T_COLORS['NO_COLOR']
    print TO_PRINT

    time.sleep(100.0 / 1000.0)
    API_DATA = chunk_read(urllib2.urlopen(API_URL), report_hook=chunk_report)
    XML_DATA = untangle.parse(API_DATA)

    TO_PRINT = T_COLORS['INFO'] + 'DATA DOWNLOADED!!!' + T_COLORS['NO_COLOR']
    print TO_PRINT

    # SAVE HISTORY TO FILE

    save_data(HISTORY_SAVE_DIR + '/vodostanje' + TIMESTAMP + '.xml', API_DATA)
    TO_PRINT = T_COLORS['INFO'] + 'HISTORY SAVED!!!' + T_COLORS['NO_COLOR']
    print TO_PRINT

# PARSE DATA

ENTRIES = XML_DATA.feed.entry
ENTRY_SIZE = len(ENTRIES)

OLD_STATE = {}
if os.path.isfile(STATE_SAVE_FILE):
    OLD_STATE = load_obj(STATE_SAVE_FILE)
    TO_PRINT = T_COLORS['INFO'] + 'OLD STATE READ!!!' + T_COLORS['NO_COLOR']
    print TO_PRINT

PRINT_STRING = '\n' + SEPARATOR

for i in range(0, ENTRY_SIZE):
    TITLE = ENTRIES[i].title.cdata[6:]

    FORMAT = '{:<' + \
        smart_str(32 - len(TITLE[:TITLE.index(' - ')].strip())) + '}'
    TITLE = TITLE[:TITLE.index(' - ')].strip() + \
        ' - ' + FORMAT.format(TITLE[TITLE.index(': ') + 2:].strip())

    JSON_TITLE = smart_str(TITLE).strip()

    TITLE = T_COLORS['TITLE'] + TITLE + T_COLORS['NO_COLOR']
    if JSON_TITLE in OLD_STATE and not ARGS.save:
        TITLE += T_COLORS['WARNING'] + \
            '{:>5}'.format(OLD_STATE[JSON_TITLE]) + ' cm  '

    SUMMARY = ENTRIES[i].summary.cdata.split(';')
    DEFENCE = SUMMARY[5:]
    DEFENCE[0] = re.sub(r" (.*):", "", DEFENCE[0].strip().lower())
    DEFENCE[1] = re.sub(r" (.*):", "", DEFENCE[1].strip().lower())
    SUMMARY = SUMMARY[:5]

    if ARGS.all or JSON_TITLE.startswith('DUNAV'):
        PRINT_STRING = PRINT_STRING + TITLE + \
            T_COLORS['DEFENCE'] + '(ODBRANA: ' + DEFENCE[0] + ', ' + DEFENCE[1] + ')\n' + \
            T_COLORS['NO_COLOR']

    for j in range(0, len(SUMMARY)):
        if ': ' in SUMMARY[j]:
            SUMMARY[j] = SUMMARY[j][SUMMARY[j].index(': ') + 1:]

        SUMMARY[j] = SUMMARY[j].strip().split(' ')
        TMP = SUMMARY[j]
        SUMMARY[j] = SUMMARY[j][0] + ' ' + '{:<22}'.format(SUMMARY[j][1]) + \
            ' ' + '{:>5}'.format(SUMMARY[j][2]) + ' cm'

        if j == 0:
            OLD_STATE[JSON_TITLE] = smart_str(TMP[2])
        if ARGS.all or JSON_TITLE.startswith('DUNAV'):
            PRINT_STRING = PRINT_STRING + '     ' + SUMMARY[j] + '\n'
            if j == len(SUMMARY) - 1:
                PRINT_STRING += SEPARATOR

print T_COLORS['NO_COLOR'] + PRINT_STRING

# SAVE STATE
if ARGS.save:
    if os.path.isfile(STATE_SAVE_FILE):
        os.rename(STATE_SAVE_FILE, STATE_SAVE_FILE + '.bup')
    save_obj(STATE_SAVE_FILE, OLD_STATE)
    TO_PRINT = T_COLORS['INFO'] + 'STATE SAVED!!!\n' + T_COLORS['NO_COLOR']
    print TO_PRINT
