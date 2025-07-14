# Hey there! 👋

I am **Shantanu Mishra**, a.k.a. **[8hantanu](wiki/self/about#8hantanu)** across the web. 

A systems software engineer based in Hyderabad, primarily working on simulation at [AMD](https://www.amd.com).
In my leisure, I try to make new things at [Yree](https://yree.io).

A minimalist who enjoys reading and thrives on running.
I find myself mostly writing and organizing — this website being a testament to that!
Whenever I get a chance, I love to [travel](wiki/self/experiences/travel/) and experience new things.

## Quick links

- **[wiki](wiki)** — my collection of random things
- **[feed](feed)** — posts from my bsky feed
- **[yree](https://yree.io)** — things I make
- **<a href="#" id="wander">wander</a>** — are you feeling lucky?

> **"We write to taste life twice, in the moment and in retrospect."**
>
> -- Anaïs Nin

Feel free to hit me up.

<script>
  document.addEventListener('DOMContentLoaded', function () {
    const wander = document.getElementById('wander');
    if (wander) {
      wander.addEventListener('click', async function (e) {
        e.preventDefault();
        try {
          const resp = await fetch('/sitemap.xml');
          if (!resp.ok) throw new Error('Could not fetch sitemap');
          const xml = await resp.text();
          const parser = new DOMParser();
          const doc = parser.parseFromString(xml, 'application/xml');

          const urls = Array.from(doc.querySelectorAll('url > loc'))
                            .map(el => el.textContent)
                            .filter(u => u && u.startsWith(location.origin));

          if (!urls.length) throw new Error('No URLs found');

          const choice = urls[Math.floor(Math.random() * urls.length)];
          window.location.href = choice;
        } catch (err) {
          console.error(err);
          alert('Something went wrong. Try again later.');
        }
      });
    }
  });
</script>
