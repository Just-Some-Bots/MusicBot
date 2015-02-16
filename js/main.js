jQuery(function() {
  var $sidebar = $('#sidebar'),
    $nav = $('.nav'),
    $main = $('.main');

  $(window).on("scroll", function(evt) {
    fixSidebar();
    setActiveSidebarLink();
  });

  $('pre').each(function(i, block) {
    hljs.highlightBlock(block);
  });

  $('.code-viewer').each(function(i) {

      $(this).prepend( "<ul class=\"languages\"></ul>" );
      $el = $(this);
      $languages = $el.find('.languages');
      $el.find('pre').css('display', 'none');
      $el.find('pre').first().css('display', 'block');

      $el.find('pre').each(function(j){
        $languages.append("<li><a href=\"#\">" + $(this).attr('data-language') + "</a></li>");
      })

      $languages.find('a').first().addClass('active');

      $el.find('a').click(function() {
        $el = $(this).closest('.code-viewer');
        $el.find('pre').css('display', 'none');
        $el.find('pre').eq($(this).parent().index()).css('display', 'block');

        $el.find('.languages').find('a').removeClass('active');
        $(this).addClass('active');

        return false;
      });
  });

  setActiveSidebarLink();

  function fixSidebar() {
    var top = window.scrollY,
      nav_height = $('.nav-bar').height();

    top = top - nav_height - 20;
    if (top < nav_height - 32) {
      top = 8;
    }

    if (top < $main.offset().top + $main.height() - $sidebar.height()) {
      $sidebar.css('top', top);
    }

    $sidebar.css('height', window.innerHeight - 30);
  };


  function setActiveSidebarLink() {
    if ($('.multi-page').length == 0) {
      $('.sidebar a').removeClass('active');
        var $closest = getClosestHeader();
        $closest.addClass('active');
        document.title = $closest.text();
    } else {
      if ($('.sidebar a.active').length == 0) {
        $('.sidebar a:first').addClass('active');
      }
    }
  }
});

function getClosestHeader() {
  var $links = $('.sidebar a'),
  top = window.scrollY,
  $last = $links.first();



  if (top < 300) {
    return $last;
  }

  for (var i = 0; i < $links.length; i++) {
    var $link = $links.eq(i),
    href = $link.attr("href");

    if (href != undefined && href.charAt(0) === "#" && href.length > 1) {
      var $anchor = $(href);

      if ($anchor.length > 0) {
        var offset = $anchor.offset();

        if (top < offset.top - 300) {
          return $last;
        }

        $last = $link;
      }
    }
  }
  return $last;
};
