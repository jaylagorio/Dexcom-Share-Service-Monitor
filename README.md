# Dexcom Share Service Monitor
 
## Introduction
This is a very rough version of a Python service to monitor whether the Dexcom Share service is running. It tries to login and, if it succeeds, posts a message on Facebook and Twitter if the service was previously down. If it was previously up and is now down it posts a message to that effect too. If the service status hasn't changed between runs it doesn't post anything to avoid alert fatigue.

## Environment Variables
The script requires the following environment variables to be created:

- `DEXCOM_ACCOUNT_NAME`: The username you use to log into the Dexcom Share app
- `DEXCOM_PASSWORD`: The password you use to log into the Dexcom Share app - if at any time you change this via the app you will need to change it in the environment variables as well
- `FACEBOOK_PAGE_ID`: The Page ID of the Facebook page you want statuses to be posted to. Your Access Token will require certain permissions to this page listed below
- `FACEBOOK_ACCESS_TOKEN`: The Facebook Access Token registered via the App you plan to be when the script posts, the App will need the `manage_pages` and `publish_pages` permissions
- `TWITTER_CONSUMER_TOKEN`: The Consumer Token provided by the Twitter platform
- `TWITTER_CONSUMER_SECRET`: The Consumer Secret provided by the Twitter platform
- `TWITTER_ACCESS_TOKEN`: The Access Token provided by the Twitter platform
- `TWITTER_ACCESS_SECRET`: The Access Secret provided by the Twitter platform

## Execution
Once you add the above environment variables you can invoke the script as follows:

```
python dexcom_connection_test.py
```

## Conclusion and Thanks
Thanks to [The Nightscout Foundation](https://www.nightscoutfoundation.org/) for giving us the opportunity to compete for [this bounty](https://www.facebook.com/NightscoutFoundation/posts/3170040823071192) during The Great Dexcom Share Blackout of 2019. Hopefully it will help people be more aware of whether the Dexcom services are working at any given time. I cribbed heavily from the following prior work:

- [Dexcom\_Tools](https://github.com/jerm/dexcom_tools/) by Jeremy Price
- [Four Simple Steps To Post To Twitter Using Python](https://www.mattcrampton.com/blog/step_by_step_tutorial_to_post_to_twitter_using_python/) by Matt Crampton
- [How to Write a Post on Facebook Using Python](https://stackoverflow.com/questions/48579740/how-to-write-a-post-on-facebook-using-python), asked by [sowmya](https://stackoverflow.com/users/8770153/sowmya) and answered by himself
