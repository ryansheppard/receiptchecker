Pretty much just scans receipts and tries to parse it in to generic items and categories along with prices. This was only tested with my grocery store, Hannaford, so results may vary. It seems to get the details right and often gets items right. Some things are named poorly on the receipt, so the frontend lets you fix that.

You need an Anthropic API key to use this.

The frontend is totally vibe coded because that is not my strong suit. The Anthropic Python library is somewhat frustrating and poorly documented, so I had to scrounge together a few random examples from the internet. 

The frontend includes a dashboard with some breakdowns and the ability to change item names. Finding similar items does not really work and I do not feel like adding OpenAI embeddings to this.
