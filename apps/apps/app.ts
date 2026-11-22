import type { Answer, Result, Sources } from './app.contract.d.ts';
import { convex } from '@exact/convex';
import { getFunctionName, makeFunctionReference } from 'convex/server';
import { convexToJson, jsonToConvex } from 'convex/values';

const origin = import.meta.env.CONVEX_ORIGIN;
export const grants = `net.websocket ${origin}`;

const client = convex(origin, { getFunctionName, convexToJson, jsonToConvex });
const getCounter = makeFunctionReference<'query', Record<string, never>, Result<'counter'>>('counter:get');
const incrementCounter = makeFunctionReference<'mutation', Record<string, never>, null>('counter:increment');

const sources: Sources = {
  greeting: ([name]): Result<'greeting'> => ({ text: `Hello from ${name}.` }),
  live: () => client.live(),
  counter: ([rev]) => client.query(rev, getCounter, {}),
  increment: async () => {
    await client.mutation(incrementCounter, {});
    return { ok: true };
  },
};
export const answer: Answer = (source, args, store, storage, native) =>
  sources[source](args, store, storage, native);
