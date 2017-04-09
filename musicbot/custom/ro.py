import re
import os
import requests
import urllib, json
import asyncio
import concurrent.futures
import time


from .common import *
from lxml import html
from functools import partial

RO_MOB_SEARCH_PAGE = 'http://www.divine-pride.net/database/monster?Name=&Map=&Item=&Scale=&Element=&Race=&minLevel=1&maxLevel=200&minFlee=1&maxFlee=800&minHit=1&maxHit=1600&Flag=&Page=1'
API_LINK = 'http://www.divine-pride.net/api/database/DBTYPE/ID?apiKey=MYKEY'
RACE_MAP = {
                '0': 'Formless',
                '1': 'Undead',
                '2': 'Brute',
                '3': 'Plant',
                '4': 'Insect',
                '5': 'Fish',
                '6': 'Demon',
                '7': 'Human',
                '8': 'Angel',
                '9': 'Dragon',
                'formless': '0',
                'undead': '1',
                'brute': '2',
                'plant': '3',
                'insect': '4',
                'fish': '5',
                'demon': '6',
                'human': '7',
                'angel': '8',
                'dragon': '9'
            }



ELE_TYPE_MAP = {
                        '0': 'Neutral',
                        '1': 'Water',
                        '2': 'Earth',
                        '3': 'Fire',
                        '4': 'Wind',
                        '5': 'Poison',
                        '6': 'Holy',
                        '7': 'Dark',
                        '8': 'Ghost',
                        '9': 'Undead',
                        'neutral': '0',
                        'water': '1',
                        'earth': '2',
                        'fire': '3',
                        'wind': '4',
                        'poison': '5',
                        'holy': '6',
                        'dark': '7',
                        'ghost': '8',
                        'undead': '9'
                    }

ELE_LVL_MAP = {
                    '0': '',
                    '2': '1',
                    '4': '2',
                    '6': '3',
                    '8': '4'
                }

SCALE_MAP = {
            '0': 'Small',
            '1': 'Medium',
            '2': 'Large',
            'small': '0',
            'medium': '1',
            'large': '2'
        }

DROP_RATE_MAX = 100

KEY = open(os.path.join(os.path.dirname(__file__), 'key.txt')).read().split('=')[1].strip()

if not KEY:
    print("WARNING: Divine Pride RO API will not work without a key")

async def cmd_ms(self, channel, author, leftover_args):
    """ 
    Usage:
        {command_prefix}ms <mob name>,<item name>

    Search results relating to mobs that drop a particular item.
    """
    search_string = ' '.join([*leftover_args]).split(',')

    mob_search = '+'.join(search_string[0].strip().split(' '))
    item_search = '+'.join(search_string[1].strip().split(' '))
    print(mob_search)
    print(item_search)

async def cmd_mi(self, channel, author, leftover_args):
    """ 
    Usage:
        {command_prefix}mi <mob name or mob id>

    If provided a valid ID, returns mob information of that mob ID.
    If provided a list of keywords, try and search it,
    If search returns multiple results, display it
    If search returns only one result, take that and return mob 
    information
    """

    if not leftover_args:
        return

    w_args = len(leftover_args)

    # if user provides a valid mob id,
    # grab the JSON of data
    if leftover_args and w_args == 1 and leftover_args[0].isdigit():
        this_mob_id = leftover_args[0]

    # if user doesn't provide a valid mob id,
    # we search website and return all results
    elif leftover_args:

        keywords = {
            'Item': ['d', 'drops', 'i', 'item'],
            'Element': ['e', 'ele', 'element'],
            'Scale': ['s', 'size'],
            'Race': ['r', 'race'],
            'Limit': ['-']
                    }
        url_replace = {
            'Item=': 'Item=',
            'Name=': 'Name=',
            'Element=': 'Element=',
            'Scale=': 'Scale=',
            'Race=': 'Race='
                    }

        mob_query = ' '.join([*leftover_args]).split(',')
        print(mob_query)

        mob_query = [query.split() for query in mob_query]
        print(mob_query)

        url_replace['Name='] += '+'.join(mob_query[0])
        print(url_replace['Name='])

        print(mob_query)

        item_bool = False
        index_min_bool = False
        index_max_bool = False
        index_set = {'min': -1, 'max': -1}


        for sub_query in mob_query[1:]:
            print('\n')
            if sub_query[0] in keywords['Item']:
                url_replace['Item='] += '+'.join(sub_query[1:])
                print(url_replace['Item='])
                item_bool = True
            
            elif sub_query[0] in keywords['Element']:
                url_replace['Element='] += ('%2C').join([ELE_TYPE_MAP[ele] for ele in sub_query[1:] if ele in ELE_TYPE_MAP])
                print(url_replace['Element='])

            elif sub_query[0] in keywords['Race']:
                url_replace['Race='] += ('%2C').join([RACE_MAP[race] for race in sub_query[1:] if race in RACE_MAP])
                print(url_replace['Race='])
            elif sub_query[0] in keywords['Scale']:
                url_replace['Scale='] += ('%2C').join([SCALE_MAP[scale] for scale in sub_query[1:] if scale in SCALE_MAP])
                print(url_replace['Scale='])

            elif sub_query[0].isdigit():
                index_min_bool = True
                index_set['min'] = int(sub_query[0])
                print('min')
                print(index_set['min'])

            elif sub_query[1] in keywords['Limit']:
                if sub_query[0].isdigit():
                    index_min_bool = True
                    index_set['min'] = int(sub_query[0])
                if sub_query[2].isdigit():
                    index_max_bool = True
                    index_set['max'] = int(sub_query[2])

                print('min')
                print(index_set['min'])
                print('max')
                print(index_set['max'])

            elif sub_query[0] in keywords['Limit']:
                if sub_query[1].isdigit():
                    index_max_bool = True
                    index_set['max'] = int(sub_query[1])
                    print('max')
                    print(index_set['max'])



            


        rep = dict((re.escape(k), v) for k, v in url_replace.items())
        pattern = re.compile("|".join(rep.keys()))
        mob_search_url = pattern.sub(lambda m: rep[re.escape(m.group(0))], RO_MOB_SEARCH_PAGE)
        print(mob_search_url)
        page = requests.get(mob_search_url)
        tree = html.fromstring(page.content)

        try:
            hrefs = tree.xpath('//tbody/tr')
            index_limit = {
            'min': 0,
            'max': len(hrefs)
                }

            print(index_limit)

        except IndexError:
            reply_text = "No results from search."
            print(reply_text)
            return Response(reply_text)

        if index_min_bool:
            index_limit['min'] = index_set['min']
        if index_max_bool:
            index_limit['max'] = index_set['max']

        hrefs = hrefs[index_limit['min']:index_limit['max']]
        print(len(hrefs))
        if len(hrefs) != 1:
            i = 0
            content = []

            mob_names = [h.xpath('.//td')[1].xpath('.//text()')[1] for h in hrefs]
            mob_ids = [h.xpath('.//td/a')[0].attrib['href'].rsplit('/', 2)[1] for h in hrefs]

            results = "__**Results**__\n"

            if item_bool:
                mob_items = [h.xpath('.//td')[13][1].xpath('.//text()')[0] for h in hrefs]
                mob_items_id = [h.xpath('.//td/a')[1].attrib['href'].rsplit('/', 2)[1] for h in hrefs]
                mob_items_rate = [h.xpath('.//td')[14].xpath('.//span/text()')[0] for h in hrefs]
                mob_list = ['**' + name + ':** ' + mob_id + \
                            ', drop: ' + drop + '(' + item_id + ') rate: ' + rates + \
                            '\n' for name, mob_id, drop, item_id, rates in zip(mob_names, mob_ids, mob_items, mob_items_id, mob_items_rate)]
            else:
                mob_list = ['**' + name + ':** ' + mob_id + '\n' for name, mob_id in zip(mob_names, mob_ids)]

            results += ''.join(mob_list)
            return Response(results)

        # If, however, there is only one result,
        # grab the id instead as it is effectively the same 
        # as querying for mob id
        else:
            this_mob_id = hrefs[0].xpath('.//td/a')[0].attrib['href'].rsplit('/', 2)[1]


    mob_url = dpapi_url_make('Monster', [this_mob_id])  
    print(mob_url)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mob_data = loop.run_until_complete(many_json_grab(mob_url))[0]

    results = await mob_print(mob_data)

    return Response(results)


async def mob_print(mob_data):
    
    mob_drops_ids = [str(i['itemId']) for i in mob_data['drops']]

    print(mob_drops_ids)
    # async queries all the items of the mob
    mob_drops_urls = dpapi_url_make('Item', mob_drops_ids)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mob_drops = loop.run_until_complete(many_json_grab(mob_drops_urls))

    
    # mapping scale, race and elemental wbers to its corresponding word equivalent
    mob_scale = SCALE_MAP[str(mob_data['stats']['scale'])]
    mob_race = RACE_MAP[str(mob_data['stats']['race'])]
    mob_ele_type = ELE_TYPE_MAP[str(mob_data['stats']['element'] % 10)]
    mob_ele_lvl = ELE_LVL_MAP[str(mob_data['stats']['element'] // 10)]
    mob_ele = mob_ele_type + " " + mob_ele_lvl

    # stitch attack damage
    mob_atk = mob_data['stats']['attack']

    SRE_LEN = 20
    STAT_LEN = 40

    # name - id
    stats = "```Markdown" + "\n" + "# " + mob_data['name'] + " - " + str(mob_data['id']) + "\n\n"

    # scale, race, element
    stats += '  ' + \
             '{:<{w}}'.format('[Scale](' + mob_scale + ')', w=SRE_LEN) + \
             '{:<{w}}'.format('[Race](' + mob_race + ')', w=SRE_LEN) + \
             '{:<{w}}'.format('[Element](' + mob_ele + ')', w=SRE_LEN) + '\n'

    # level, attack
    stats += '  ' + \
             '{:<{w}}'.format('[Level](' + str(mob_data['stats']['level']) + ')', w=STAT_LEN) + \
             '{:<{w}}'.format('[Attack](' + str(mob_atk['minimum']) + ' - ' + str(mob_atk['maximum']) + ')', w=STAT_LEN) + '\n'
    # health, attack range
    stats += '  ' + \
             '{:<{w}}'.format('[Health](' + str(mob_data['stats']['health']) + ')', w=STAT_LEN) + \
             '{:<{w}}'.format('[Range](' + str(mob_data['stats']['attackRange']) + ')', w=STAT_LEN) + '\n'
    
    # move speed, attack speed
    stats += '  ' + \
             '{:<{w}}'.format('[Move Speed](' + str(mob_data['stats']['movementSpeed']) + ' ms)', w=STAT_LEN) + \
             '{:<{w}}'.format('[Attack Speed](' + str(mob_data['stats']['attackSpeed']) + ' ms)', w=STAT_LEN) + '\n'

    # aggro range, escape range
    stats += '  ' + \
             '{:<{w}}'.format('[Aggro Range](' + str(mob_data['stats']['aggroRange']) + ')', w=STAT_LEN) + \
             '{:<{w}}'.format('[Escape Range](' + str(mob_data['stats']['escapeRange']) + ')', w=STAT_LEN) + '\n'

    stats += '\n  ' + \
             '<drops>' + '\n'

    for item1, item2, name1, name2 in zip(mob_data['drops'][0::2], mob_data['drops'][1::2], mob_drops[0::2], mob_drops[1::2]):
        stats += '  ' + \
                 '{:<{w}}'.format('[' + str(item1['itemId']) + ']('  + name1['name'] + ')[' \
                    + str(item1['chance']/DROP_RATE_MAX) + '%]', w=STAT_LEN) + \
                 '{:<{w}}'.format('[' + str(item2['itemId']) + ']('  + name2['name'] +')[' \
                    + str(item2['chance']/DROP_RATE_MAX) + '%]', w=STAT_LEN) + '\n'


    stats += "```"

    print(stats)

    return stats


    # makes the url and returns it
def dpapi_url_make(db_type, ids):
    results = []
    for the_id in ids:
        rep = {'DBTYPE': db_type, 'ID': the_id, 'MYKEY': KEY}  
        rep = dict((re.escape(k), v) for k, v in rep.items())
        pattern = re.compile("|".join(rep.keys()))
        results.append(pattern.sub(lambda m: rep[re.escape(m.group(0))], API_LINK))

    return results

    # takes a list of urls and performs json requests concurrently


async def many_json_grab(urls):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:

        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(
                executor,
                partial(
                    requests.get, 
                    i, headers={'Accept-Language': 'en-US'}
                    )
                )
            for i in urls
        ]
        for response in await asyncio.gather(*futures):
            results.append(response.json())

    return results


    # Nova RO Signatures
async def cmd_sig(self, channel, author, leftover_args):
    """
    Usage:
        {command_prefix}sig <character name 1>,<character name 2>,<>,...

    The bot return Nova RO sigatures of character names listed.
    """
    if leftover_args:
        sig_bg = 10
        sig_pose = 12
        full_string = ' '.join([*leftover_args])
        sig_list = full_string.split(',')
        sig_link = 'https://www.novaragnarok.com/ROChargenPHP/newsig/'
        reply_text = ""

        for string in sig_list:
            string = string.strip()
            print (string)
            string_list = string.split(' ')

            sig_bg_val = str(randint(1, sig_bg))
            sig_pose_val = str(randint(1, sig_pose))

            
            name_list = [s for s in string_list if not '/' in s]
            char_name = '_'.join(name_list)
            bgpose_val = [s for s in string_list if '/' in s]
            

            if bgpose_val:
                bgpose_list = bgpose_val[0].split('/')
                print(bgpose_list)

                if bgpose_list[0] and bgpose_list[0].isdigit():
                    sig_bg_val = bgpose_list[0]

                if bgpose_list[1] and bgpose_list[1].isdigit():
                    sig_pose_val = bgpose_list[1]


            reply_text += sig_link + char_name + '/' + sig_bg_val + '/' + sig_pose_val + '?' + str(round(time.time())) + '\n'

        return Response(reply_text)
