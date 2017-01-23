// Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
// Licensed under GPLv3, see file LICENSE in the top directory

$(function() {
    function foldBlock(elements) {
        elements.removeClass('unfolded-block').addClass('folded-block');
    }

    function unfoldBlock(elements) {
        elements.removeClass('folded-block').addClass('unfolded-block');
    }

    function onFoldBlock() {
        foldBlock($(this).closest('div.block'));
    }

    function onUnfoldBlock() {
        unfoldBlock($(this).closest('div.block'));
    }

    $('div#output').on('click', 'button.fold-top', onFoldBlock);
    $('div#output').on('click', 'button.fold-bottom', onFoldBlock);
    $('div#output').on('click', 'button.unfold', onUnfoldBlock);

    $('button#fold-functions').click(function() { foldBlock($('div.source > div.block')); });
    $('button#unfold-functions').click(function() { unfoldBlock($('div.source > div.block')); });
    $('button#fold-all').click(function() { foldBlock($('div.block')); });
    $('button#unfold-all').click(function() { unfoldBlock($('div.block')); });


    function showCode(enabled) {
        if (enabled) {
            $('div.source').addClass('show-only-code');
        }
        else {
            $('div.source').removeClass('show-only-code');
        }
    }

    function showLevelColors(enabled) {
        if (enabled) {
            $('div.source').addClass('show-level-colors');
        }
        else {
            $('div.source').removeClass('show-level-colors');
        }
    }

    function showIndentGuides(enabled) {
        if (enabled) {
            $('div.source').addClass('show-indent-guides');
        }
        else {
            $('div.source').removeClass('show-indent-guides');
        }
    }

    $('input#only-code').change(function() {
        showCode(this.checked);
    });

    $('input#level-colors').change(function() {
        showLevelColors(this.checked);
    });

    $('input#indent-guides').change(function() {
        showIndentGuides(this.checked);
    });

    // Ensure state corresponds to checkbox button states on page reload
    showCode($('input#only-code').prop('checked'));
    showLevelColors($('input#level-colors').prop('checked'));
    showIndentGuides($('input#indent-guides').prop('checked'));


    function scrollToTarget() {
        var target = $(':target').get(0);
        if (target) {
            target.scrollIntoView(true);
        }
    }

    $(window).on('hashchange', scrollToTarget);

    // Also scroll on reload, since browser may not do that
    scrollToTarget();

    $('div#output').on('click', 'a.link-def', function() {
        // Inject a history location at the clicked line
        // so it's easy to navigate back to it
        var line = $(this).closest('div.line');
        window.location.hash = '#' + line.get(0).id;
    });
});
