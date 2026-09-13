<script setup lang="ts">
import type { RealmId } from './realms';
defineProps<{ page: number; active: RealmId | null }>();
</script>

<template>
  <!-- Shared scenery is separate from, and cannot steal clicks from, the eight destinations. -->
  <svg class="continuous-ink" :class="active && `lit-${active}`" viewBox="0 0 600 600" preserveAspectRatio="none" aria-hidden="true" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
    <g class="wide-composition" v-if="page===0">
      <g class="paper-ridge trail-text">
        <path d="M66 209C145 219 204 196 258 167L306 124 337 147 373 135 405 166M257 168l52-27 26 10 39-16m-68-11 3 17m28 6-2 4"/>
        <path class="faint" d="M33 225c107 24 176-1 235-39l42-30 27 5 35-13m-112 44 54-19 28 0 37-14M301 142l-8 27m17-24-8 26m15-23-8 21"/>
      </g>
      <g class="construction-plane trail-questions">
        <path d="M352 152C381 92 455 82 527 137M354 148l-6 13 15-2M320 286l101-35 148 13M367 277l70 18 135-26M408 282l-12 67M437 295l-20 73"/>
        <path class="faint" d="m404 265 94 10m-107-5 89 11m-126-79 10-11m-13 4 9 7m165-103-5 16M329 284l-15 5m83 1-2 7"/>
      </g>
      <g class="ink-river trail-notes">
        <path d="M79 475C25 502 74 531 143 518S239 457 284 423"/>
        <path class="faint" d="M132 529c63-2 103-48 142-82M40 508q17 27 59 25"/>
        <path d="m192 478 34-65 85-32-19 67m-79-23 77-31m-72 41 29-13" class="faint"/>
      </g>
      <g class="neutral-bridge"><path d="M284 423c32-24 56-47 40-64-12-13-35-3-21 7s55 4 85-22c62-55 136-67 238-54"/><path class="faint" d="M274 447c39-34 64-55 71-76M350 379c74-61 144-83 264-70"/></g>
      <g class="shoreline trail-review">
        <path d="M270 494c25-13 42-6 57-11m112 5c36 8 79-1 113-10M279 538c54 8 79-3 111-9 54-10 126 6 168-12"/>
        <path class="faint" d="M312 549c60 7 82-10 126-11m-48 21c58 3 90-6 136-5m-48-67 44 6m-53 4 32 2"/>
      </g>
    </g>
    <g class="wide-composition" v-else>
      <g class="orbital-arc trail-preview">
        <path d="M-26 290C63 302 111 284 159 253S259 188 321 174c59-13 91-33 110-60"/>
        <path class="faint" d="M-22 310c94 12 150-19 198-47s97-58 142-72M37 154C21 83 101 16 181 42m-43-4 1 9m-67 7 5 8m-37 20 7 5"/>
      </g>
      <g class="desk-architecture trail-advice">
        <path d="m296 254 104 34 170-46m-267 19 97 33 166-43M315 95l-8 98m8-98 67-24 139 38m-139-38-4 33"/>
        <path class="faint" d="M334 104l49-18 116 30"/>
      </g>
      <g class="neutral-bridge"><path d="M400 294l-4 82m167-123-11 75"/><path class="faint" d="M317 270l-9 61m205-66-4 44M325 326l64 24m23 22 100-28"/></g>
      <g class="garden-terrain trail-expand">
        <path d="M28 518c49-21 88-20 123-11m95 5c55-6 80-30 107-48s41-25 80-12m-116 38c60-2 89-10 113-24"/>
        <path d="M145 531c34 7 50 10 79-3m-57 10-13 21-23 9m47-24 7 24 30 11m-25-18 21-10m-21 12-4 19M55 525c-11 16-21 18-31 19"/>
        <path class="faint" d="M30 552c23-9 51-13 74-12m129 13c44-7 70-27 89-34m-74 53c55-19 87-32 120-31M261 522l28 4m-18-14 24 4m-11-13 21 4"/>
      </g>
      <g class="distant-landing trail-progress">
        <path d="m341 440 57-39 24 7m-35 46 65-45 22 6M374 468l42-25M472 484l70-30 29 11M482 494l60-25 29 10m-29-25v15m22-6v11"/>
        <path class="faint" d="M339 433l54-42 20 7m94-47 49-38 22 9v52m-22-61-3 58m-44 97-4 41m14-46-2 27M368 485l45-33"/>
      </g>
    </g>
    <!-- On narrow leaves the same motifs turn vertically through the alternating drawings. -->
    <g class="narrow-composition" v-if="page===0">
      <path class="trail-text" d="M46 115c176 25 276 9 367-20l80 11m-138 23 114 15-35 43"/>
      <path class="trail-questions" d="M475 201c77 18 38 68-67 88l-88 15-44 42m69-70 106 12"/>
      <path class="trail-notes" d="M109 403c-86 32-15 78 93 61s115-51 159-75"/>
      <path d="M361 389c79-43 148-59 264-66M189 467c98-4 208-17 280 19"/>
      <path class="trail-review" d="M82 578c92-19 155 6 219-1s121-16 192-10"/>
    </g>
    <g class="narrow-composition" v-else>
      <path class="trail-preview" d="M95 54c-89 81 41 125 178 108s240-34 271-68M50 138c61 42 175 50 266 32"/>
      <path class="trail-advice" d="m212 281 140 33 191-32m-186 34-12 69M-24 323c121 2 164-33 236-42"/>
      <path class="trail-expand" d="M80 435c99-23 214 22 303-5m-210 15-45 32m116-30 51 26M259 455c100-20 195-10 231 35"/>
      <path class="trail-progress" d="m47 574 102-33 106 23m84 8 141-28m-46 15 5 23"/>
    </g>
  </svg>
</template>

<style scoped>
.continuous-ink{position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none;color:#c3d3dd;stroke-width:.85;opacity:.72}
.continuous-ink g[class*="trail"],.neutral-bridge,.narrow-composition path{opacity:.38;transition:opacity .2s,color .2s,filter .2s}
.faint{opacity:.43;stroke-width:.65}
.lit-text .trail-text,.lit-questions .trail-questions,.lit-notes .trail-notes,.lit-review .trail-review,.lit-preview .trail-preview,.lit-advice .trail-advice,.lit-expand .trail-expand,.lit-progress .trail-progress{opacity:.65;color:var(--realm-accent)}
.narrow-composition{display:none}
@media(max-width:700px){.wide-composition{display:none}.narrow-composition{display:block}.continuous-ink{stroke-width:1.2;opacity:.62}}
@media(prefers-reduced-motion:reduce){.continuous-ink g,.continuous-ink path{transition:none}}
</style>
