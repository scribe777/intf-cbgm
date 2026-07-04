<template>
  <div class="vm-local-stemma card-slidable">
    <div class="card-header">
      <toolbar :toolbar="toolbar">
        <button-group slot="right" :options="options.png_dot" />
      </toolbar>
    </div>

    <div class="svg-wrapper" @contextmenu.prevent="on_contextmenu">
      <d3stemma ref="engine" prefix="ls_" />
    </div>

    <context-menu ref="menu" @input="on_menu_input" />
    <alert ref="alert" />
  </div>
</template>

<script>
/**
 * This module implements the local stemma with drag-and-drop editing.
 *
 * @component client/local_stemma
 * @author Marcello Perathoner
 */

import { select, selectAll, event } from 'd3-selection';
import { drag }                     from 'd3-drag';
import { groupBy }                  from 'lodash';

import d3_stemma_layout from 'd3_stemma_layout.vue';
import tools            from 'tools';
import alert            from 'widgets/alert.vue';
import button_group     from 'widgets/button_group.vue';
import context_menu     from 'widgets/context_menu.vue';
import toolbar          from 'widgets/toolbar.vue';
import { mkmsg }        from 'widgets/context_menu.vue';
import { options }      from 'widgets/options';

const SVG_X_BORDER = 40;  // in pixel
const SVG_Y_BORDER = 40;


/** @var {D3selector} dragged_node - The node being dragged or null */
let dragged_node = null;
/** @var {D3selector} target_node  - The node under the node being dragged or null */
let target_node  = null;

/**
 * Moves the node back to the original position.
 *
 * If the user drops the node 'nowhere' then this function slides the node
 * back to the original position.
 *
 * @param {D3selector} d3_node - The node to slide back.
 */

function return_to_base (d3_node) {
    if (d3_node !== null) {
        const d = d3_node.datum ();
        const n = d3_node.node ();
        n.velocity ({
            'transform' : [`translate(${d.pos.orig_x},${d.pos.orig_y})`, `translate(${d.pos.x},${d.pos.y})`],
        }, {
            'duration' : 250,
            'easing'   : 'ease-in-out',
        }).then (() => {
            d.pos.x = d.pos.orig_x;
            d.pos.y = d.pos.orig_y;
        });
    }
}

/**
 * Highlight or unhighlight a node
 *
 * @param {Object} node - The node to highlight
 * @param {bool}   b    - Whether to highlight or unhighlight
 */

function highlight (node, b) {
    if (node) {
        node.classed ('highlight', b);
    }
}

/**
 * Drag and drop handler
 *
 * Creates a d3-drag object that implements the drag-and-drop local stemma
 * editor.
 *
 * @param {Object} vm - The Vue instance
 */

function drag_listener (vm) {
    return drag ()
        .on ('start', function (dummy_d) {
            // do nothing (yet)
        })
        .on ('drag', function (d) {
            if (dragged_node === null) {
                dragged_node = select (this);
                d.pos.orig_x = d.pos.x;
                d.pos.orig_y = d.pos.y;
                // Suppress the mouseover event on the node being dragged
                // otherwise it will absorb the event and the underlying
                // node will not get it.
                dragged_node.attr ('pointer-events', 'none');
                dragged_node.raise ();
                target_node = null;
                // console.log ('dragging ' + dragged_node.datum ().label);
            }
            d.pos.x += event.dx;
            d.pos.y += event.dy;
            dragged_node.attr ('transform', 'translate(' + d.pos.x + ',' + d.pos.y + ')');
        })
        .on ('end', function (dummy_d) {
            const dragged_node_ref = dragged_node;
            if (target_node) {
                // if dropped on another node, the default action is to
                // move, but if the shift key was held down, the action will
                // be to merge or to split
                let action = 'move';
                if (event.sourceEvent.ctrlKey) {
                    action = 'add';
                }
                if (event.sourceEvent.shiftKey) {
                    action = (dragged_node.datum ().labez === target_node.datum ().labez)
                        ? 'merge' : 'split';
                }
                vm.post ('stemma-edit/' + vm.pass_id, {
                    'action'     : action,
                    'labez_old'  : dragged_node.datum ().labez,
                    'clique_old' : dragged_node.datum ().clique,
                    'labez_new'  : target_node.datum ().labez,
                    'clique_new' : target_node.datum ().clique,
                }).then (() => {
                    vm.$trigger ('epoch');
                }).catch ((error) => {
                    vm.$refs.alert.show (error.response.data.message, 'error');
                    return_to_base (dragged_node_ref);
                });
                highlight (target_node, false);
            } else {
                // if dropped on no mans land
                return_to_base (dragged_node_ref);
            }
            if (dragged_node !== null) {
                dragged_node.attr ('pointer-events', 'auto');
            }
            dragged_node = null;
            target_node = null;
        });
}

/**
 * Implements the context menu.
 *
 * The context menu can be used to split the attestation, reassign source
 * nodes or to merge a split.
 *
 * @param {Object} evt - The event
 * @param {Vue}    vm  - The Vue instance
 */

async function build_contextmenu (evt, vm) {
    const dataset = evt.target.dataset;
    const data = {
        'labez_old'  : dataset.labez,
        'clique_old' : dataset.clique,
    };

    const response = await vm.get ('cliques.json/' + vm.pass_id);

    const cliques = response.data.data.filter (o => o.labez[0] !== 'z')
        .concat ([
            { 'labez' : '*', 'clique' : '1', 'labez_clique' : '*' },
            { 'labez' : '?', 'clique' : '1', 'labez_clique' : '?' },
        ]);

    const actions = [];

    // Menu Header
    actions.push ({
        'msg'   : mkmsg ('Reading', data.labez_old, data.clique_old),
        'bg'    : data.labez_old,
        'class' : 'disabled',
        'data'  : {
            ... data,
            'action'   : '',
            'disabled' : true,
        },
    });

    // Split one clique

    actions.push ({
        'msg'   : mkmsg ('Split', data.labez_old, data.clique_old),
        'bg'    : data.labez_old,
        'class' : '',
        'data'  : {
            ... data,
            'action'     : 'split',
            'labez_new'  : '?',
            'clique_new' : '1',
        },
    });

    // Merge two cliques

    for (const c of cliques) {
        if ((c.labez === data.labez_old) && (c.clique !== data.clique_old)) {
            actions.push ({
                'msg'   : mkmsg ('Merge into', c.labez, c.clique),
                'bg'    : data.labez_old,
                'class' : '',
                'data'  : {
                    ... data,
                    'action'     : 'merge',
                    'labez_new'  : c.labez,
                    'clique_new' : c.clique,
                },
            });
        }
    }

    // Reassign Source of clique

    for (const c of cliques) {
        if (c.labez !== data.labez_old || c.clique !== data.clique_old) {
            actions.push ({
                'msg'   : mkmsg ('Set Source to', c.labez, c.clique),
                'bg'    : c.labez,
                'class' : '',
                'data'  : {
                    ... data,
                    'action'     : 'move',
                    'labez_new'  : c.labez,
                    'clique_new' : c.clique,
                },
            });
        }
    }

    // Add another source

    for (const c of cliques) {
        if (c.labez !== data.labez_old || c.clique !== data.clique_old) {
            actions.push ({
                'msg'   : mkmsg ('Add Source', c.labez, c.clique),
                'bg'    : c.labez,
                'class' : '',
                'data'  : {
                    ... data,
                    'action'     : 'add',
                    'labez_new'  : c.labez,
                    'clique_new' : c.clique,
                },
            });
        }
    }

    // Delete a source

    const graph_vm = vm.get_graph_vm ();
    const g = graph_vm.graph;
    for (const edge of g.edges) {
        const t_labez = g.nodes[edge.elems[1].id].attrs.labez;
        if (t_labez === dataset.labez) {
            const s_attr = g.nodes[edge.elems[0].id].attrs;
            actions.push ({
                'msg'   : mkmsg ('Remove Source', s_attr.labez, s_attr.clique),
                'bg'    : s_attr.labez,
                'class' : '',
                'data'  : {
                    ... data,
                    'action'        : 'del',
                    'source_labez'  : s_attr.labez,
                    'source_clique' : s_attr.clique,
                },
            });
        }
    }

    return groupBy (actions, a => a.data.action);
}

/**
 * Load a new passage.
 *
 * @param {Vue}    vm      - The Vue instance
 * @param {Number} pass_id - Which passage to load.
 *
 * @return {Promise} Promise, resolved when the new passage has loaded.
 */
function load_passage (vm, pass_id) {
    if (pass_id === 0) {
        return;
    }

    const graph_vm = vm.get_graph_vm ();
    const wrapper = vm.$el.querySelector ('.svg-wrapper');

    const requests = [
        vm.get ('passage.json/' + vm.pass_id),
        vm.get (vm.build_url ('stemma.dot')),
        tools.fade_out (wrapper).promise,
    ];
    Promise.all (requests).then ((responses) => {
        vm.passage = responses[0].data.data;
        const bbox = graph_vm.load_dot (responses[1].data);
        wrapper
            .velocity ({
                'width'  : (bbox.width  + SVG_X_BORDER),
                'height' : (bbox.height + SVG_Y_BORDER),
            }, tools.velocity_opts)
            .velocity ({
                'opacity' : 1.0,
            }, tools.velocity_opts);

        if (vm.$store.getters.can_write) {
            // Drag a node.
            selectAll ('div.vm-local-stemma g.node.draggable')
                .call (drag_listener (vm));
            selectAll ('div.vm-local-stemma g.node.droptarget')
                .on ('mouseover', function (dummy_d) {
                    if (dragged_node && select (this) !== dragged_node) {
                        target_node = select (this);
                        highlight (target_node, true);
                    }
                })
                .on ('mouseout', function (dummy_d) {
                    if (dragged_node && select (this) !== dragged_node) {
                        highlight (target_node, false);
                        target_node = null;
                    }
                });
        }
        draw_ghosts (vm);
        emit_stemma_state (vm);
    });
}

/**
 * Overlay the AI's proposed edges as dashed "ghost" arrows on the current
 * stemma (drawn source -> reading).  Re-run after every load_dot (the graph is
 * rebuilt each reload) and whenever the proposal changes.  An edge whose source
 * matches the current stemma renders muted (the AI concurs); one that would
 * rewire a reading renders in the AI accent.
 */
function draw_ghosts (vm) {
    const gvm = vm.get_graph_vm ();
    if (!gvm || !gvm.$el || !gvm.graph) return;
    const svg = select (gvm.$el);
    svg.select ('g.ai-ghosts').remove ();
    const edges = vm.ai_edges;
    if (!edges || !edges.length) return;
    const nodes = gvm.graph.nodes;

    const pos_of = (labez) => {
        let fallback = null;
        for (const k in nodes) {
            const a = nodes[k].attrs;
            if (!a || !a.pos) continue;
            if (a.labez === labez) {
                if (a.clique === '1' || a.clique == null) return a.pos;
                fallback = fallback || a.pos;
            }
        }
        return fallback;
    };
    // current source per target reading, to flag agree vs. change
    const cur = {};
    for (const e of (gvm.graph.edges || [])) {
        const s = nodes[e.elems[0].id], t = nodes[e.elems[1].id];
        if (s && t && s.attrs && t.attrs) cur[t.attrs.labez] = s.attrs.labez;
    }

    const outer = svg.select ('g');   // the translated group holding the nodes
    if (outer.empty ()) return;
    const layer = outer.append ('g').attr ('class', 'ai-ghosts');

    for (const e of edges) {
        if (!e.reading || !e.source) continue;
        // Only ghost *real* suggestions — edges that differ from the current
        // stemma.  An edge that already matches ('agrees') is not a suggestion,
        // so a dotted line over the existing correct path is just noise.  The
        // node pulse on hover still identifies an agreeing edge's endpoints.
        if (cur[e.reading] === e.source) continue;
        const a = pos_of (e.source), b = pos_of (e.reading);
        if (!a || !b || (a.x === b.x && a.y === b.y)) continue;
        layer.append ('path')
            .attr ('class', 'ai-ghost change')
            .attr ('data-reading', e.reading)
            .attr ('data-source', e.source)
            .attr ('d', 'M' + a.x + ',' + a.y + ' L' + b.x + ',' + b.y);
    }
    // the graph was just rebuilt — reapply any active card-hover emphasis
    emphasize_ghost (vm);
}

/**
 * Emphasise the ghost edge the user is hovering in the AI suggestion panel and
 * pulse its two nodes — the source amber, the reading green.  This mirrors the
 * collation editor's orange-source / green-target cell pulse when hovering a
 * regularization suggestion card.  Driven by the `ai_hover` prop.
 */
function emphasize_ghost (vm) {
    const gvm = vm.get_graph_vm ();
    if (!gvm || !gvm.$el) return;
    const svg = select (gvm.$el);

    // clear previous emphasis
    svg.selectAll ('.ai-ghost').classed ('emph', false).classed ('dim', false);
    svg.selectAll ('ellipse.node').classed ('ai-src-hi', false).classed ('ai-tgt-hi', false);

    const h = vm.ai_hover;
    if (!h) return;

    // pulse the source (amber) and reading (green) nodes — always, so an
    // already-correct edge (which has no ghost) is still identified on hover
    svg.selectAll ('ellipse.node').each (function () {
        const lz = this.getAttribute ('data-labez');
        if (lz === h.source)  select (this).classed ('ai-src-hi', true);
        if (lz === h.reading) select (this).classed ('ai-tgt-hi', true);
    });

    // spotlight this edge's ghost only if one is drawn (change edges only);
    // don't dim the real suggestions when hovering an agreeing card
    const match = svg.selectAll ('.ai-ghost').filter (function () {
        return this.getAttribute ('data-reading') === h.reading;
    });
    if (!match.empty ()) {
        svg.selectAll ('.ai-ghost').classed ('dim', true);
        match.classed ('dim', false).classed ('emph', true).raise ();
    }
}

/**
 * Emit the current stemma as a { reading: sourceLabez } map so the AI
 * suggestion panel can tell which of its proposed edges are real changes vs.
 * already-selected paths.  Re-emitted on every (re)load, so it stays current
 * after edits.
 */
function emit_stemma_state (vm) {
    const gvm = vm.get_graph_vm ();
    if (!gvm || !gvm.graph) return;
    const nodes = gvm.graph.nodes;
    const cur = {};
    for (const e of (gvm.graph.edges || [])) {
        const s = nodes[e.elems[0].id], t = nodes[e.elems[1].id];
        if (s && t && s.attrs && t.attrs) cur[t.attrs.labez] = s.attrs.labez;
    }
    vm.$trigger ('stemma_state', cur);
}


export default {
    'props'      : ['pass_id', 'epoch', 'global', 'var_only', 'ai_edges', 'ai_hover'],
    'components' : {
        'alert'        : alert,
        'button-group' : button_group,
        'context-menu' : context_menu,
        'toolbar'      : toolbar,
        'd3stemma'     : d3_stemma_layout,
    },
    'data' : function () {
        return {
            'passage' : {},
            'options' : options,
            'toolbar' : {
                'dot' : () => { this.download ('stemma.dot'); },
                'png' : () => { this.download ('stemma.png'); },
            },
        };
    },
    'watch' : {
        pass_id () {
            this.load_passage ();
        },
        epoch () {
            this.load_passage ();
        },
        ai_edges () {
            // proposal changed (or cleared) — re-overlay without a full reload
            draw_ghosts (this);
        },
        ai_hover () {
            // hovered card changed — re-emphasise without redrawing the ghosts
            emphasize_ghost (this);
        },
        'toolbar' : {
            handler () {
                this.load_passage ();
            },
            'deep' : true,
        },
    },
    'methods' : {
        load_passage () {
            load_passage (this, this.pass_id);
        },
        get_graph_vm () {
            return this.$refs.engine;
        },
        build_url (page) {
            const vm = this;

            // provide a width and fontsize for GraphViz to format the graph
            const cstyle = getComputedStyle (vm.$el);
            const params = {
                'width'    : parseFloat (cstyle.getPropertyValue ('width')), // in px
                'fontsize' : parseFloat (cstyle.getPropertyValue ('font-size')), // in px
            };
            return `${page}/${vm.pass_id}?` + tools.param (params);
        },
        async on_contextmenu (evt) {
            if (this.$store.getters.can_write) {
                if (evt.target.closest ('.node.draggable')) {
                    this.$refs.menu.open (await build_contextmenu (evt, this), evt.target);
                }
            }
        },
        on_menu_input (data) {
            const vm = this;

            vm.post ('stemma-edit/' + vm.pass_id, data)
                .then (() => {
                    vm.$trigger ('epoch');
                }).catch ((error) => {
                    vm.$refs.alert.show (error.response.data.message, 'error');
                });
        },
        download (page) {
            window.open (this.build_full_api_url (this.build_url (page), '_blank'));
        },
    },
    'mounted' : function () {
        this.load_passage ();
    },
};
</script>


<style lang="scss">
/* local_stemma.vue */
@import "bootstrap-custom";

div.vm-local-stemma {
    marker.link {
        visibility: hidden !important;
    }
}

/* AI-proposed "ghost" edges overlaid on the stemma (see draw_ghosts). */
g.ai-ghosts {
    pointer-events: none;

    .ai-ghost {
        fill: none;
        stroke-width: 3.4;
        stroke-linecap: round;
        stroke-dasharray: 6 5;
        animation: ai-ghost-march 1s linear infinite;

        &.change {
            stroke: #8b6df0;
            filter: drop-shadow(0 0 3px rgba(139, 109, 240, 0.55));
        }
        &.agrees {
            stroke: #5aa073;
            opacity: 0.65;
        }

        /* when a suggestion card is hovered: fade the others, spotlight this one */
        &.dim  { opacity: 0.15; }
        &.emph {
            opacity: 1;
            stroke-width: 5;
        }
    }
}
@keyframes ai-ghost-march {
    to { stroke-dashoffset: -18; }
}

/* Nodes pulsed while hovering an AI suggestion card: source amber, reading
   green — the stemma analogue of the collation editor's reg-cell pulse.  We
   animate stroke-width + a glow filter (not just colour) so the pulse reads
   clearly regardless of the node's labez colouring. */
div.vm-local-stemma ellipse.node.ai-src-hi {
    stroke: #ff6f00 !important;
    animation: ai-node-pulse-src 1.1s ease-in-out infinite;
}
div.vm-local-stemma ellipse.node.ai-tgt-hi {
    stroke: #2e7d32 !important;
    animation: ai-node-pulse-tgt 1.1s ease-in-out infinite;
}
@keyframes ai-node-pulse-src {
    0%, 100% { stroke-width: 3px; stroke-opacity: 0.85; }
    50%      { stroke-width: 7px; stroke-opacity: 1; }
}
@keyframes ai-node-pulse-tgt {
    0%, 100% { stroke-width: 3px; stroke-opacity: 0.85; }
    50%      { stroke-width: 7px; stroke-opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
    div.vm-local-stemma ellipse.node.ai-src-hi,
    div.vm-local-stemma ellipse.node.ai-tgt-hi { animation: none; }
}
@media (prefers-reduced-motion: reduce) {
    g.ai-ghosts .ai-ghost { animation: none; }
}

</style>
