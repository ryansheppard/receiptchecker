Pretty much just scans receipts and tries to parse it in to generic items and categories along with prices. This was only tested with my grocery store, Hannaford, so results may vary. It seems to get the details right and often gets items right. Some things are named poorly on the receipt, so the frontend lets you fix that.

You need an Anthropic API key and `gspread` to have a configured service account with access to the sheet in question.

The frontend is totally vibe coded because that is not my strong suit. The Anthropic Python library is somewhat frustrating and poorly documented, so I had to scrounge together a few random examples from the internet. This probably doesn't need `pola.rs`, but I may move from Sheets to a custom dashboard.
