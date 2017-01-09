import re
import os
import requests
import urllib, json
import asyncio
import concurrent.futures


from .common import *
from lxml import html

# RO LINK CONSTANTS

RO_MOB_PAGE = 'http://www.divine-pride.net/database/monster/'
RO_PAGE = 'http://www.divine-pride.net/'
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
                '9': 'Dragon'
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
                        '9': 'Undead'
                    }

ELE_LVL_MAP = {
                    '0': '',
                    '2': '1',
                    '4': '2',
                    '6': '3'
                }

SCALE_MAP = {
            '0': 'Small',
            '1': 'Medium',
            '2': 'Large'
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
#     rep = {"condition1": "", "condition2": "text"} # define desired replacements here

# # use these three lines to do the replacement
# rep = dict((re.escape(k), v) for k, v in rep.iteritems())
# pattern = re.compile("|".join(rep.keys()))
# text = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)

    if not leftover_args:
        return

    w_args = len(leftover_args)

    # if user provides a valid mob id,
    # grab the JSON of data
    if leftover_args and w_args == 1 and leftover_args[0].isdigit():
        this_mob_id = leftover_args[0]

        



    # if user doesn't provide a valid mob id,
    # we search website first and grab first result
    # then use it to go to mob page
    elif leftover_args:

        mob_search_name = '+'.join([*leftover_args])
        mob_search_url = RO_MOB_SEARCH_PAGE.replace("Name=", "Name=" + mob_search_name)
        page = requests.get(mob_search_url)
        tree = html.fromstring(page.content)

        try:
            hrefs = tree.xpath('//tbody/tr/td/a')
        except IndexError:
            reply_text = "No results from search."
            print(reply_text)
            return Response(reply_text)

        if len(hrefs) != 1:
            mob_ids = [href.attrib['href'].rsplit('/', 2)[1] for href in hrefs]
            mob_names = [href.xpath('text()')[0] for href in hrefs]

            results = "__**Results**__\n"
            mob_list = ['**' + mob_name.strip() + ':** ' + mob_id + '\n' for mob_name, mob_id in zip(mob_names, mob_ids)]
            results += ''.join(mob_list)
            return Response(results)

        else:
            pass


    mob_url = dpapi_url_make('Monster', [this_mob_id])  
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mob_data = loop.run_until_complete(many_json_grab(mob_url))[0]


    for pair in mob_data:
        print(pair)

    results = await mob_print(mob_data)

    return Response(results)


        

    # headvals = ['{:<25}'.format('[' + l_header.strip() + '](' + l_value.strip() + ')') + \
    #             '{:<35}'.format('[' + r_header.strip() + '](' + r_value.strip() + ')') + '\n' \
    #             for r_header, r_value, l_header, l_value in \
    #             zip(r_headers, r_values, l_headers, l_values)]
    # stats +=  ''.join(headvals) + "```"

async def mob_print(mob_data):
    
    mob_drops_ids = []
    for i in mob_data['drops']:
        mob_drops_ids.append(str(i['itemId']))

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


    MAX_CHAR_LINE = 70
    SRE_LEN = 20
    STAT_LEN = 35

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
                requests.get, 
                i
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

            
            if len(string_list) > 2:
                sig_bg_txt = string_list[-2]
                sig_pose_txt = string_list[-1]

                if sig_bg_txt.isdigit():
                    sig_bg_val = sig_bg_txt
                    del string_list[-1]
                if sig_pose_txt.isdigit():
                    sig_pose_val  = sig_pose_txt
                    del string_list[-1]

                print (string_list)
                char_name = '_'.join(string_list)
                
            else:
                char_name = '_'.join(string_list)

            reply_text += sig_link + char_name + '/' + sig_bg_val + '/' + sig_pose_val + '\n'

        return Response(reply_text)
