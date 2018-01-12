---
title: Authentication
position: 2
right_code: |
  ~~~ javascript
  $.get("http://api.myapp.com/books/", { "token": "YOUR_APP_KEY"}, function(data) {
    alert(data);
  });
  ~~~
  {: title="jQuery" }

  ~~~ bash
  curl http://api.myapp.com/books?token=YOUR_APP_KEY
  ~~~
  {: title="Curl" }
---

You need to be authenticated for all API requests. You can generate an API key in your developer dashboard.

Add the API key to all requests as a GET parameter.

Nothing will work unless you include this API key
{: .error }
