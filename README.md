# bannerServices

An OpenLP plugin that creates a sermon banner: a title, Bible verses, and an icon (AI-generated or hand-made), shown at the start of each sermon.

This project has two goals:

1. **Product:** a working OpenLP plugin, used personally and by a church that already runs OpenLP, and published as open source.
2. **Software factory experiment:** learn to design agent systems that resolve backlog tasks automatically. The human acts as product manager and builds the factory, and measures the cost of code that actually works.

## Working assumption (not yet confirmed)

From OpenLP, the user picks a title, verses, and an icon. The plugin generates a banner slide or image and inserts it into the service order, right before the sermon.

## Open questions

- Is this the intended flow? The detailed product idea is still pending.
- Should the banner also be exported as a standalone image, for example for social media?
- Icon source: which AI image service, or manual upload only?
- Which OpenLP version does the church run?

## Plan

1. **Product:** write the spec and the backlog. The backlog is the factory's raw material.
2. **First slice by hand:** set up OpenLP locally, learn how plugins load and how to test them (Python + PyQt), and build one small feature end to end.
3. **Factory:** turn the repeated steps into a pipeline: issue → spec → TDD implementation → review → quality gates → PR.
4. **Measure:** cost per merged change, gate pass rate, and rework.

## Environment notes (2026-10-13)

- OpenLP is not installed on the dev machine yet.
- Python 3.12.14 is available.
- To verify: OpenLP plugins are Python/PyQt modules that live under `openlp/plugins/` in the OpenLP source tree. Check the docs to see whether there is an external plugin install mechanism.

## References

- [Latent Space: Zach Lloyd on software factories](https://www.latent.space/p/software-factories)
- [Warp Factories announcement](https://fortune.com/press-releases/warp-launches-warp-factories-automate-software-development-2026-08-18/)
- [Cortex: What is an AI software factory?](https://www.cortex.io/post/what-is-an-ai-software-factory)
- [Paulund: Build factories, not features](https://paulund.co.uk/notebook/ai/software-factory-build-factories-not-features)
