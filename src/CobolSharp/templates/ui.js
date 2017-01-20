// Copyright 2016 Peter Liljenberg <peter.liljenberg@gmail.com>
// Licensed under GPLv3, see file LICENSE in the top directory

$(function() {
    function onFoldClick() {
        var block = $(this).closest('div.block');

        // Flip this block
        block.removeClass('unfolded-block').addClass('folded-block');
    }

    function onUnfoldClick() {
        var block = $(this).closest('div.block');
        block.removeClass('folded-block').addClass('unfolded-block');
    }

    $('div#output').on('click', 'button.fold-top', onFoldClick);
    $('div#output').on('click', 'button.fold-bottom', onFoldClick);
    $('div#output').on('click', 'button.unfold', onUnfoldClick);
});
