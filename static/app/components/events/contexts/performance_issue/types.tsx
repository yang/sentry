export enum TraceKnownDataType {
  TRACE_ID = 'trace_id',
  SPAN_ID = 'span_id',
  PARENT_SPAN_ID = 'parent_span_id',
  OP_NAME = 'op',
  STATUS = 'status',
  TRANSACTION_NAME = 'transaction_name',
}

/**
         "caught_on_span": scope.span.span_id,
                    "caught_on_transaction": self.transaction_id,
                    "counts": counts,
                    "times": times.total_seconds() * 1000,
                    "op": exception.get('op'),
                    "desc": exception.get('desc'),
 */

export type TraceKnownData = {
  desc: string;
  caught_on_span?: string;
  caught_on_transaction?: string;
  counts?: string;
  op?: string;
  times?: string;
};

export type FocusedSpanIDMap = Record<string, Set<string>>;
