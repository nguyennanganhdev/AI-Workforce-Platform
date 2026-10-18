/**
 * Whether the work list is asked for again on this 5-second tick.
 * A visible tab asks every tick. A hidden tab still asks every sixth tick (30 seconds): the count in its title
 * is how a person on another page learns that work was offered. Nothing is asked while a change is being saved.
 */
export function shouldPoll(tick: number, hidden: boolean, locked: boolean): boolean {
  return !locked && (!hidden || tick % 6 === 0);
}
