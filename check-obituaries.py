import os
import requests
from tiny_jmap_library import TinyJMAPClient
import logging
import schedule
import time

FASTMAIL_TOKEN = os.environ.get('FASTMAIL_TOKEN')
FASTMAIL_FROM = os.environ.get('FASTMAIL_FROM')
FASTMAIL_TO = os.environ.get('FASTMAIL_TO')
FASTMAIL_TO_GREETING = os.environ.get('FASTMAIL_TO_GREETING')

LAST_NAMES = os.environ.get('LAST_NAMES')

NO_RESULTS_TEMPLATE = 'Your search for "<span style=\'color:#FD6717\'>{}</span>" did not find any obituaries in this newspaper.'

# date range 99999 - All, 1 - Today
SEARCH_URL_TEMPLATE = 'https://www.legacy.com/obituaries/rapidcity/obituary-search.aspx?daterange=1&lastname={}&countryid=1&stateid=54&affiliateid=1334'

# Enable logging
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')


def sendEmail(lastName, searchUrl):
    jmapClient = TinyJMAPClient(
        hostname='api.fastmail.com',
        username=FASTMAIL_FROM,
        token=FASTMAIL_TOKEN
    )

    account_id = jmapClient.get_account_id()
    query_res = jmapClient.make_jmap_call(
        {
            "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
            "methodCalls": [
                [
                    "Mailbox/query",
                    {"accountId": account_id, "filter": {"name": "Drafts"}},
                    "a",
                ]
            ],
        }
    )

    draft_mailbox_id = query_res["methodResponses"][0][1]["ids"][0]
    assert len(draft_mailbox_id) > 0

    body = """
    Hi {}.

    A member from the {} family has passed away.
        
    Here are the search results:
    {}

    ---

    Generated by your check-obituaries.py.
    """.format(FASTMAIL_TO_GREETING, lastName, searchUrl)

    draft = {
        "from": [{"email": FASTMAIL_FROM}],
        "to": [{"email": FASTMAIL_TO}],
        "subject": "A member of the {} family has passed away.".format(lastName),
        "keywords": {"$draft": True},
        "mailboxIds": {draft_mailbox_id: True},
        "bodyValues": {"body": {"value": body, "charset": "utf-8"}},
        "textBody": [{"partId": "body", "type": "text/plain"}],
    }

    identity_id = jmapClient.get_identity_id()

    results = jmapClient.make_jmap_call(
        {
            "using": [
                "urn:ietf:params:jmap:core",
                "urn:ietf:params:jmap:mail",
                "urn:ietf:params:jmap:submission",
            ],
            "methodCalls": [
                ["Email/set", {"accountId": account_id,
                               "create": {"draft": draft}}, "a"],
                [
                    "EmailSubmission/set",
                    {
                        "accountId": account_id,
                        "onSuccessDestroyEmail": ["#sendIt"],
                        "create": {
                            "sendIt": {
                                "emailId": "#draft",
                                "identityId": identity_id,
                            }
                        },
                    },
                    "b",
                ],
            ],
        }
    )


def job():
    logging.info('Running job...')
    lastNames = LAST_NAMES.split(',')
    numberOfFoundObituaries = 0

    for lastName in lastNames:
        # Obituary GET
        searchResults = requests.get(SEARCH_URL_TEMPLATE.format(lastName), headers={
            'User-Agent': 'Mozilla/5.0 (iPhone14,3; U; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/19A346 Safari/602.1'})
        if searchResults.text.find(NO_RESULTS_TEMPLATE.format(lastName)) == -1:
            sendEmail(lastName, SEARCH_URL_TEMPLATE.format(lastName))
            numberOfFoundObituaries += 1

    if numberOfFoundObituaries == 0:
        logging.info('No new obituary was found.')
        logging.info('Job finished.')
    else:
        logging.info('{} obituaries have been found.'.format(
            str(numberOfFoundObituaries)))
        logging.info('Job finished.')


schedule.every().day.at('15:00').do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
