# Automate checking in volunteers from service into check-in.

## Code Structure
This code essentially grabs the most upcoming check-in event, finds a corresponding future service plan and then finds all the confirmed/unconfirmed volunteers from that service and checks them in in that check-in event.


The code is broken into two parts. First part is getting all the volunteers for a corresponding check in time using the PCO API. The second part is posting all the volunteers to API via logging into the PCO website, as there is no public API endpoints at the moment.

### Input
The input is a dictionary with the keys: 
* service_name: A string with the name of the service_type you want to use.
* event_name: A string with the name of the event you want to use.
* location_name: A string of the name of the location you want to check-in for this event. If there is no locations then make this a empty string “”.  

### Process

1. Get a mapping of name to id of the event and service_type
2. Get the ids of the service_name, event_name and location_name, using the input and the mappings
3. Get the next upcoming event_period_id and corresponding event_times. 
4. Get the next upcoming future service plan and corresponding plan times. 
5. Check if all the event times are within the service plan times otherwise get the next future service plan.
6. Grab all the volunteers for the matching service plan and make a list of dictionaries ready to be posted to the API. 
7. Create a request session and GET the PCO login website
8. Grab the corresponding csrf token key from the website and using this and the login creds POST to the PCO login website to login in. (The request session will save all your cookies)
9. Bulk check in each volunteer by POSTing to the coresponding bulk_check_in endpoint/url. 

## Automating this using Google Cloud Platform
You can automate this process by making this code a Cloud Function on google cloud platform. It’s pretty cheap. You can then set up a google Cloud Schedular which posts a HTTP request to the cloud function at a regular interval, i.e every Sunday Morning at 6am. 
