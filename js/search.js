jQuery(function() {
  var $search = $("#search"),
  $search_results = $("#search_results");

  if ($('.multi-page').length == 0) {
    var data = $.getJSON('/search_data.json');
  } else {
    var data = $.getJSON('/search_data_multi.json');
  }

  $(document).click(function(event) {
    if(!$(event.target).closest('#search_results').length && !$(event.target).closest('#search').length) {
        if( $search_results.is(":visible")) {
            $search_results.hide();
        }
    }
  });

  $( document ).on( "click", "#search_results a", function() {
    $search_results.hide();
  });

  window.idx = lunr(function () {
    this.field('id');
    this.field('title', { boost: 10 });
    this.field('description');
    this.field('type');
  });

  data.then(function(data){
    $.each(data, function(index, value){
      window.idx.add(
        $.extend({ "id": index }, value)
      );
    });
  });


  $search.keyup(function() {
    perform_search();
  }).focus(function() {
    perform_search();
  });

  function perform_search() {
    var query = $search.val();

    if (query === ''){
      $search_results.hide();
    } else {
      var results = window.idx.search(query);
      data.then(function(data) {

        if (results.length) {
          $search_results.empty().append('<ul>');
          results.forEach(function(result) {
            var appendString = "<li><a href='";
            if ($('.multi-page').length == 0) {
              appendString += '#';
            }

            appendString += result.ref + "'>";
            appendString += data[result.ref].title;
            if (data[result.ref].type != '') {
              appendString += "<span class='endpoint " + data[result.ref].type + "'></span> ";
            }

            if (data[result.ref].description != '') {
              appendString += "<span class='description'>" + data[result.ref].description + "</span>";
            }
            appendString += "</a></li>";
            $search_results.append(appendString);
          });
          $search_results.append('</ul>').show();
        } else {
          $search_results.html('<ul><li style="padding: 5px">No results found</li></ul>').show();
        }
      });
    }
  }
});
