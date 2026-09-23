// Source-pixel constraints: parallel rails and vertical (constant X) transitions.
export function railY(rails, x) {
  const [a,b] = rails.upper;
  return a[1] + (x-a[0])*(b[1]-a[1])/(b[0]-a[0]);
}
export function railPoints(rails) {
  if (rails.upper.length !== 2 || !(rails.depth > 0)) return [];
  const [a,b] = rails.upper, direction = Math.sign(b[0]-a[0]);
  if (!direction) return [];
  const stations = [...new Set(rails.transitions)].filter(x => x > Math.min(a[0],b[0]) && x < Math.max(a[0],b[0])).sort((x,y)=>(x-y)*direction);
  let lower = !rails.startsUpper;
  const point = x => [x, railY(rails,x)+(lower?rails.depth:0)];
  const points = [point(a[0])];
  for (const x of stations) { points.push(point(x)); lower=!lower; points.push(point(x)); }
  points.push(point(b[0]));
  return points;
}
export function railHandles(rails) {
  const handles=rails.upper.map((p,i)=>({kind:'upper',index:i,point:p}));
  if(rails.upper.length===2 && rails.depth>0){
    const x=(rails.upper[0][0]+rails.upper[1][0])/2;
    handles.push({kind:'depth',point:[x,railY(rails,x)+rails.depth]});
    rails.transitions.forEach((x,index)=>handles.push({kind:'transition',index,point:[x,railY(rails,x)+rails.depth/2]}));
  }
  return handles;
}
