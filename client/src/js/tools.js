/**
 * This module implements helper functions and is a container for all stuff
 * that doesn't fit elsewhere.
 *
 * @module client/tools
 * @author Marcello Perathoner
 */

import { pick }  from 'lodash';
import qs        from 'qs';
import Velocity  from 'velocity-animate/velocity';

Velocity.defaults.duration = 250;
const velocity_opts = { 'duration' : 250 };


/**
 * Format a string in python fashion.  "{count} items found"
 *
 * @function format
 *
 * @param {String} s  - The string to format
 * @param {dict} data - A dictionary of key: value
 *
 * @returns {String} The formatted string
 */

export function format (s, data) {
    return s.replace (/\{([_\w][_\w\d]*)\}/gm, (match, p1) => data[p1]);
}

/**
 * Transform a string so that numbers in the string sort naturally.
 *
 * Transform any contiguous run of digits so that it sorts
 * naturally during an alphabetical sort. Every run of digits gets
 * the length of the run prepended, eg. 123 => 3123, 123456 =>
 * 6123456.
 *
 * @function natural_sort
 *
 * @param {String} s - The input string
 *
 * @returns {String} The transformed string
 */

export function natural_sort (s) {
    return s.replace (/\d+/g, (match, dummy_offset, dummy_string) => match.length + match);
}

const qs_options = {
    'arrayFormat' : 'brackets',
    'skipNulls'   : true,
};

/**
 * Parse a query string.
 *
 * @function deparam
 *
 * @param {String} query_string - A string in the form "p=1&q=2"
 *
 * @returns {Object} { p : 1, q : 2 }
 */

export function deparam (query_string) {
    return qs.parse (query_string, qs_options);
}

/**
 * Build a query string.
 *
 * @function param
 *
 * @param {Object} params    - Object of params, eg. { p : 1, q : 2 }
 * @param {Array}  pick_list - Pick only these members, eg. ['p', 'q']
 *
 * @returns {String} - A string in the form "p=1&q=2"
 */

export function param (params, pick_list = null) {
    return qs.stringify ((pick_list ? pick (params, pick_list) : params), qs_options);
}

export function set_hash (params, pick_list = null) {
    window.location.hash = '#' + param (params, pick_list);
}

export function get_hash () {
    // FIXME ??? window.location.hash ? window.location.hash.substring (1) : '';
    return deparam (window.location.hash.substring (1));
}

/**
 * Breadth first search in graph
 *
 * @function bfs
 *
 * @param {Object} edges - The edges list
 * @param {String} start - The start node id
 *
 * @returns A list of node ids in breadth-first order
 */

export function bfs (edges, start) {
    var ids   = [start];
    var queue = [];
    var cur   = start;
    function is_adjacent (edge) {
        return edge.elems[0].id === cur;
    }
    while (cur) {
        for (const n of edges.filter (is_adjacent)) {
            var id = n.elems[1].id;
            if (ids.indexOf (id) === -1) {
                ids.push (id);
                queue.push (id);
            }
        }
        cur = queue.shift ();
    }
    return ids;
}

export function get_scroll_height (el) {
    let height = el.scrollHeight;
    if (height === el.clientHeight) {
        // content height is smaller than element height
        const old_height = el.style.height;
        el.style.height = '1px';
        height = el.scrollHeight;
        el.style.height = old_height;
    }
    return parseInt (height, 10);
}

export function slide_fade_in (el, auto = false) {
    return el
        .velocity ({ 'height' : get_scroll_height (el) }, {
            'complete' : () => {
                if (auto) {
                    el.style.height = 'auto';
                }
            }, ... velocity_opts })
        .velocity ({ 'opacity' : 1.0 }, velocity_opts);
}

export function slide_fade_out (el) {
    // actually fade then slide out
    return el
        .velocity ({ 'opacity' : 0.0 }, velocity_opts)
        .velocity ({ 'height' : 0 }, velocity_opts);
}

export function fade_out (el) {
    return el.velocity ({ 'opacity' : 0.0 }, velocity_opts);
}

export function fade_in (el) {
    return el.velocity ({ 'opacity' : 1.0 }, velocity_opts);
}

/**
 * How stable is the genealogical direction between two witnesses?  The same
 * rule as direction_stability () in server/textflow.py.
 *
 * @param {number} older - No. of passages where W1 has the prior variant
 * @param {number} newer - No. of passages where W2 has the prior variant
 * @returns {object} flips: at how many passages the priority of the variants
 *                   would have to be turned around for the direction to vanish;
 *                   stable: false if the majority could as well be the toss of
 *                   a coin (sign test, 5 %); directed: false on equal counts.
 */

export function direction_stability (older, newer) {
    const diff = Math.abs (newer - older);
    return {
        'flips'    : Math.ceil (diff / 2),
        'stable'   : diff * diff > 3.84 * (older + newer),
        'directed' : diff > 0,
    };
}

/**
 * Say the stability of a direction in a sentence, for a tooltip.
 *
 * @param {number} prior     - No. of passages where the ancestor has the prior variant
 * @param {number} posterior - No. of passages where it has the posterior variant
 * @returns {string} The sentence
 */

export function direction_stability_title (prior, posterior) {
    const st = direction_stability (posterior, prior);
    if (!st.directed) {
        return `Prior at ${prior}, posterior at ${posterior} passages: no direction.`;
    }
    return `Prior at ${prior}, posterior at ${posterior} passages. `
        + `The direction vanishes if ${st.flips} local `
        + (st.flips === 1 ? 'stemma is' : 'stemmata are') + ' decided the other way.'
        + (st.stable ? '' : ' Unstable: a majority this narrow could be chance.');
}

export default {
    format,
    natural_sort,
    param,
    deparam,
    set_hash,
    get_hash,
    bfs,
    get_scroll_height,
    slide_fade_in,
    slide_fade_out,
    fade_in,
    fade_out,
    velocity_opts,
    direction_stability,
    direction_stability_title,
};
