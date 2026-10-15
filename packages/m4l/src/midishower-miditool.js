// Entry point for the MidiShower miditool device; see midishower-node.js.
process.env.MIDISHOWER_DEVICE = "miditool";
require("./midishower-node.js");
