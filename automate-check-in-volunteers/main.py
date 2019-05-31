import requests
from bs4 import BeautifulSoup
import base64
import logging
import os
import json
import ast


""" Set up planing centre login details """
# Your normal login details you use to login into planning centre
login_data = dict(
    email=os.environ['EMAIL'],
    password=os.environ['PASSWORD']
)

# urls
login_url = 'https://accounts.planningcenteronline.com/login'
bulk_check_url_fmt = 'https://check-ins.planningcenteronline.com/event_periods/{}/bulk_check_ins'

# Request variables
headers = {
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/67.0.3396.99 Safari/537.36',
    'x-csrf-token': None
}

""" Set up API login information """
# These are the tokens created when setting up the PCO dev app and token keys
app_id = os.environ['APP_ID']
token = os.environ['TOKEN']

# set up header for Authorization
encode_auth_header = base64.b64encode(f'{app_id}:{token}'.encode()).decode()
headers3 = { 
  'Authorization': f'Basic {encode_auth_header}', 
}
base_url = 'https://api.planningcenteronline.com/'

n_future_plans = 3


def get_service_mapping():
    """ Get mapping dict of service types
    
    Returns:
        A mapping dict which maps service types names to their ids
    """
    # Get all Service types:
    all_service_type = requests.get(base_url + 'services/v2/service_types', headers=headers3).json()
    # Make Dict of service names and ids
    service_name_to_id = {service_type['attributes']['name']:service_type['id'] for service_type in all_service_type['data']} 
    return service_name_to_id


def get_event_mapping():
    """ Get mapping dict of events
    
    Returns:
        A mapping dict which maps event names to their ids
    """
    # Get all events:
    all_events = requests.get(base_url + 'check-ins/v2/events', headers=headers3).json()
    # Make Dict of event names and ids
    event_to_id = {event['attributes']['name']:event['id'] for event in all_events['data']}   
    return event_to_id


def get_location_id(event_id, loc_name):
    """ Get location id from event id
    
    Args:
        event_id (str): event id to use to look for event periods.
        loc_name (str): The name of the location to get the id

    Returns:
        Location id given the location name. If no valid location name is given
        then empty string is returned
    """
    # Get all locations:
    all_locations = requests.get(base_url + f'check-ins/v2/events/{event_id}/locations', headers=headers3).json()
    # Make Dict of location names and ids
    location_to_id = {location['attributes']['name']:location['id'] for location in all_locations['data']} 
    # Get adult attendees location id
    location_id = location_to_id.get(loc_name, '')
    return location_id


def get_event_times(event_id):
    """ Get first event period(should be next upcoming event) and coresponding
    event times
    
    Args:
        event_id (str): event id to use to look for event periods.

    Returns:
        event peroid id and mapping dict that maps event times to their ids
    """
    r = requests.get(base_url + f'check-ins/v2/events/{event_id}/event_periods?include=event_times&per_page=1', headers=headers3).json()
    event_period_id = r['data'][0]['id']
    event_times = r['included']
    # Map the event time to even time id
    event_time_to_id = {time['attributes']['starts_at']:time['id'] for time in event_times}
    return event_period_id, event_time_to_id


def get_future_plans(service_id, indx):
    """ Get a future service plan and future service plans times
    
    Args:
        service_id (str): service type id to use to look for plans.
        indx (str): index of future plan to get with the lowest index(0) 
                    relating to cloest upcoming plan.

    Returns:
        upcoming plan id and their coresponding service plan times
    """
    # Get service type latest plan and also include plan times
    service_plans = requests.get(base_url + f'services/v2/service_types/{service_id}/plans?filter=future&order=sort_date&per_page=1&include=plan_times&offset={indx}', headers=headers3).json()
    
    # Get plan ids/plan times
    upcoming_plan_id = service_plans['data'][0]['id']
    plan_times = service_plans['included']

    # Get service time ids and times, times are in UTC time
    service_time_ids_to_time = {time['id']:time['attributes']['starts_at'] for time in plan_times if time['attributes']['time_type'] == 'service'}
    
    return upcoming_plan_id, service_time_ids_to_time


def get_volunteers(service_id, upcoming_plan_id, location_id, event_id, event_period_id, service_time_ids_to_time, event_time_to_id):
    """ get all volunteers which are confirmed/unconfirmed for upcoming event
    
    Args:
        service_id (str): service type id.
        upcoming_plan_id (str): service upcoming plan id used to find corepsonding team members
        location_id (str): event location id (i.e adult attendies)
        event_id (str): event id
        event_period_id (str): event period id
        service_time_ids_to_time (dict): Dict which maps service times to a UTC time
        event_time_to_id (dict): Dict which maps event times to a UTC time
        
    Returns:
        Returns a list of volunteers to be put into the bulk checkin
    """
    # Get all Team members
    team_members = requests.get(base_url + f'services/v2/service_types/{service_id}/plans/{upcoming_plan_id}/team_members?per_page=100', headers=headers3).json()

    volunteers = []
    # Loop through team members
    for person in team_members["data"]:
        if person["attributes"]["status"] == "C" or person["attributes"]["status"] == "U":
            # get volunteer time ids
            time_ids=person['relationships']['times']['data']
            # convert time_id into times
            times = set(service_time_ids_to_time.get(time_id['id']) for time_id in time_ids)
            # convert times into event_ids
            check_time_ids = set(event_time_to_id.get(time) for time in times)
            
            # remove any None entry
            check_time_ids.discard(None)

            for check_t_id in check_time_ids:
                temp_dict = {
                    'check-in-kind':'Volunteer',
#                     "name": person["attributes"]["name"], # you can also add the persons name but it doesn't seem to be compulsory
                    'bulk_check_in[check_ins_attributes][][account_center_person_id]': person['relationships']['person']['data']['id'],
                    'bulk_check_in[check_ins_attributes][][check_in_times_attributes][][location_id]': location_id,
                    'bulk_check_in[check_ins_attributes][][check_in_times_attributes][][event_time_id]': check_t_id,
                    'bulk_check_in[check_ins_attributes][][check_in_times_attributes][][kind]': "Volunteer",
                    'bulk_check_in[check_ins_attributes][][event_id]': event_id,
                    'bulk_check_in[check_ins_attributes][][event_period_id]': event_period_id
                }
                volunteers.append(temp_dict)
    return volunteers


def post_volunteers(data):
    """Get all the details for next upcoming event and volunteers and post them in check in
    Args:
        data (dict): dictonary that contains the desired service_name, event_name and location_name
    Returns:
        
    """
    logging.info("STARTING FUNCTION")
    
    # This was needed when want to decode http body data from googe cloud
    # when using cloud functions. This can be ignored
    # data = ast.literal_eval(request.data.decode('utf-8'))
    
    # Determine which mode we are in
    service_name = data['service_name']
    event_name = data['event_name']
    loc_name = data['location_name']
    
    logging.info(f'We are doing service: {service_name}')
    
    # Get mapping ids from api
    service_name_to_id = get_service_mapping()
    event_to_id = get_event_mapping()

    # Get Service id
    service_id = service_name_to_id[service_name]
    # Get event id
    event_id = event_to_id[event_name]
    # Get location id
    location_id = get_location_id(event_id, loc_name)
    # Get event period and event time ids
    event_period_id, event_time_to_id = get_event_times(event_id)

    # loop through and find correct service
    for i in range(n_future_plans):
        
        # Get plan times
        try:
            upcoming_plan_id, service_time_ids_to_time = get_future_plans(service_id, i)
        except IndexError:
            logging.exception(f'Ran out of services to compare with event times {event_time_to_id}')
            raise

        # Check this is the correct service plan(times should match with event time)
        if not all([event_time in service_time_ids_to_time.values() for event_time in event_time_to_id.keys()]):
            logging.warning(f'Not correct service times: {service_time_ids_to_time }')
            continue
            
		# Get volunteers attending at the event
        volunteers = get_volunteers(
			service_id,
			upcoming_plan_id,
			location_id,
			event_id,
			event_period_id,
			service_time_ids_to_time,
			event_time_to_id
		)
        break
    else:
        raise LookupError(f'Can not find future service with event times {event_time_to_id}')
        
    # Open a requests session, this is where we post the volunteers to 
    # PCO api, as no post api exists at the moment for check-in
    bulk_check_url = bulk_check_url_fmt.format(event_period_id)
    with requests.Session() as s:
        # This is where we make the first request to generate an csrf-token
        r = s.get(login_url, headers=headers)

        # Using Beautiful Soup to scrape the tokens from the page source
        soup = BeautifulSoup(r.content, 'html.parser') 

        # Here we are populating header with the csrf-token to allow for future posts
        headers["x-csrf-token"] = soup.find('meta', attrs={'name': 'csrf-token'})['content']

        # Here we login by submitting the post request with the same session passing the url, login_data, and headers
        r = s.post(login_url, data=login_data, headers=headers)

        # Posting all volunteers in check in.
        for payload in volunteers:
            check_person = s.post(bulk_check_url, data=payload, headers=headers)
            if check_person.status_code != 200:
                logging.error(f'ERROR CODE: {check_person.status_code}, when posting payload {payload}')
        
    logging.info('FINISHED FUNCTION')
    return f'Done!'

if __name__ == "__main__":
    post_volunteers(dict(service_name="Morning Service", event_name="Morning Service", location_name="Main Hall"))
