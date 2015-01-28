---
title: /books
type: get
description: List all books
parameters:
  title: List Book Format
  data:
    - offset:
      - integer
      - Offset the results by this amount
    - limit:
      - integer
      - Limit the number of books returned
right_code:
  return: |
    [
      {
        "id": 1,
        "title": "The Hunger Games",
        "score": 4.5,
        "date_added": "12/12/2013"
      },
      {
        "id": 1,
        "title": "The Hunger Games",
        "score": 4.7,
        "date_added": "15/12/2013"
      },
    ]
---

<p> Lists all the photos you have access to. You can paginate by using the parameters listed above. </p>

<div class="code-viewer">
  <pre data-language="jQuery">
  $.get('http://api.myapp.com/books/', { token: 'YOUR_APP_KEY'}, function(data) {
    alert(data);
  });</pre>

  <pre data-language="Python">
  r = requests.get('http://api.myapp.com/books/', token="YOUR_APP_KEY")
  print r.text</pre>

  <pre data-language="Node">
  var request = require('request');
  request('http://api.myapp.com/books?token=YOUR_APP_KEY', function (error, response, body) {
    if (!error &amp;&amp; response.statusCode == 200) {
      console.log(body);
    }
  })</pre>

  <pre data-language="cURL">
  curl http://sampleapi.readme.com/orders?key=YOUR_APP_KEY</pre>

</div>
