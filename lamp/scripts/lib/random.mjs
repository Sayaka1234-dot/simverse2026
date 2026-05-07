export function randomInt(min, max, random = Math.random) {
  return Math.floor(random() * (max - min + 1)) + min;
}

export function pickRandom(list, random = Math.random) {
  return list[randomInt(0, list.length - 1, random)];
}

export function repeat(length, mapper) {
  return Array.from({ length }, (_, index) => mapper(index));
}
