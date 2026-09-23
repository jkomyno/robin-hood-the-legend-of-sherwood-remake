import {test} from 'node:test';
import assert from 'node:assert/strict';
import {railPoints,railY,railHandles} from './battlement-rails.mjs';
test('transitions are vertical and rail runs stay parallel',()=>{
 const r={upper:[[10,20],[110,70]],depth:12,transitions:[80,30,50],startsUpper:true};
 const p=railPoints(r);
 assert.deepEqual(p,[[10,20],[30,30],[30,42],[50,52],[50,40],[80,55],[80,67],[110,82]]);
 for(let i=1;i<p.length-1;i+=2){assert.equal(p[i][0],p[i+1][0]);assert.equal(Math.abs(p[i][1]-p[i+1][1]),12)}
 r.depth=25;assert.equal(railPoints(r)[2][1],55);
 r.upper[1][1]=120;assert.equal(railY(r,30),40);
 assert.equal(railHandles(r).length,6);
});
test('reverse, duplicate/outside transitions, and incomplete setup',()=>{
 const r={upper:[[110,70],[10,20]],depth:12,transitions:[30,30,50,80,0,150],startsUpper:false};
 assert.deepEqual(railPoints(r),[[110,82],[80,67],[80,55],[50,40],[50,52],[30,42],[30,30],[10,20]]);
 assert.deepEqual(railPoints({...r,upper:[]}),[]);
 assert.deepEqual(railPoints({...r,depth:0}),[]);
});
