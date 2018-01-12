---
title: /books
position: 1.0
type: get
description: List all books
right_code: |
  ~~~ json
  [
    {
      "id": 1,
      "title": "The Hunger Games",
      "score": 4.5,
      "dateAdded": "12/12/2013"
    },
    {
      "id": 1,
      "title": "The Hunger Games",
      "score": 4.7,
      "dateAdded": "15/12/2013"
    },
  ]
  ~~~
  {: title="Response" }

  ~~~ json
  {
    "error": true,
    "message": "Invalid offset"
  }
  ~~~
  {: title="Error" }
---
offset
: Offset the results by this amount

limit
: Limit the number of books returned

This call will return a maximum of 100 books
{: .info }

Lists all the photos you have access to. You can paginate by using the parameters listed above.

~~~ javascript
$.get("http://api.myapp.com/books/", { "token": "YOUR_APP_KEY"}, function(data) {
  alert(data);
});
~~~
{: title="jQuery" }

~~~ python
r = requests.get("http://api.myapp.com/books/", token="YOUR_APP_KEY")
print r.text
~~~
{: title="Python" }

~~~ javascript
var request = require("request");
request("http://api.myapp.com/books?token=YOUR_APP_KEY", function (error, response, body) {
  if (!error && response.statusCode == 200) {
    console.log(body);
  }
});
~~~
{: title="Node.js" }

~~~ bash
curl http://sampleapi.readme.com/orders?key=YOUR_APP_KEY
~~~
{: title="Curl" }
