// Original, in-memory miniature books. No publication or account data is involved.
export interface Passage { title: string; kind: string; text: string; math?: string; answer?: string }
export interface SampleBook {
  id: string; title: string; short: string; subject: string; color: string;
  symbol: string; count: number; edition: string; summary: string;
  passages: Passage[];
}
export const books: SampleBook[] = [
  {
    id:'analysis', title:'Real Analysis', short:'Real Analysis', subject:'Mathematics',
    color:'#526c89',symbol:'ε',count:36,edition:'Existing demo sample',
    summary:'Foundations, integration, differentiation and sequences of functions. The existing 36-object illustrative grimoire gives this tree a longer book to hold.',
    passages:[
      {title:'Foundations',kind:'Chapter',text:'The real numbers, continuity and compactness.'},
      {title:'Integration',kind:'Chapter',text:'Riemann sums, integrability and the fundamental theorem of calculus.'},
      {title:'Differentiation',kind:'Chapter',text:'Derivatives, local behavior and the mean value theorem.'},
      {title:'Sequences of functions',kind:'Chapter',text:'Pointwise and uniform convergence.'},
    ],
  },
  {
    id:'symmetry',title:'Symmetry & Transformations',short:'Symmetry',subject:'Geometry',
    color:'#7d6694',symbol:'⬡',count:4,edition:'Short sample · 4 passages',
    summary:'A short introduction to rotations and reflections, using a regular hexagon. One definition, one rule, one worked example and one exercise.',
    passages:[
      {title:'What is a symmetry?',kind:'Definition',text:'A symmetry of a figure is a distance-preserving transformation that maps the figure onto itself. After the transformation, the figure occupies exactly the same set of points.'},
      {title:'Rotations of a regular polygon',kind:'Rule',text:'A regular n-sided polygon is unchanged by a rotation about its center through an integer multiple of 360°/n.',math:'\\theta_k=\\frac{360^\\circ k}{n},\\quad k=0,1,\\ldots,n-1'},
      {title:'A regular hexagon',kind:'Worked example',text:'For a regular hexagon, n = 6. The smallest positive rotation that preserves it is 60°. It also has six reflection axes: three pass through opposite vertices and three through midpoints of opposite sides.',math:'\\theta_1=\\frac{360^\\circ}{6}=60^\\circ'},
      {title:'Try a square',kind:'Exercise',text:'What is the smallest positive angle of rotation that maps a square onto itself? How many reflection axes does it have?',answer:'90°. It has four reflection axes: two diagonals and two lines through the midpoints of opposite sides.'},
    ],
  },
  {
    id:'light',title:'Light, Distance & Time',short:'Light & Time',subject:'Physics',
    color:'#667f83',symbol:'☼',count:4,edition:'Short sample · 4 passages',
    summary:'Use the finite speed of light to connect distance with travel time. Four brief passages, including a calculation and a question.',
    passages:[
      {title:'The speed of light',kind:'Definition',text:'Light travels in a vacuum at exactly 299,792,458 metres per second. For the estimates in this miniature, use 3.00 × 10⁸ metres per second.',math:'c=299\\,792\\,458\\;\\mathrm{m\\,s^{-1}}'},
      {title:'Distance and travel time',kind:'Equation',text:'For light traveling through a vacuum over distance d, the travel time t is the distance divided by the speed of light.',math:'d=ct,\\qquad t=\\frac{d}{c}'},
      {title:'A one-second journey',kind:'Worked example',text:'Using our rounded value of c, light travels about 300,000 kilometres in one second. Keep the units together when making the calculation.',math:'d=(3.00\\times10^8\\;\\mathrm{m\\,s^{-1}})(1.00\\;\\mathrm{s})=3.00\\times10^8\\;\\mathrm{m}'},
      {title:'A distant signal',kind:'Exercise',text:'A light signal travels 6.00 × 10⁸ metres through a vacuum. Approximately how long does the journey take?',answer:'2.00 seconds, using t = d/c and c ≈ 3.00 × 10⁸ m/s.'},
    ],
  },
];
