/** Tailwind build for the staff app (replaces the cdn.tailwindcss.com play script).
 *  Rebuild after changing templates:
 *    tailwindcss -c tailwind.config.js -i app/static/css/src/tailwind.css -o app/static/css/tailwind.css --minify
 *  Uses the Tailwind v3 standalone CLI (no Node.js needed); see README.
 */
module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/static/js/**/*.js',
    './app/modules/**/*.py',
    './app/utils/**/*.py',
  ],
  theme: { extend: {} },
  plugins: [],
};
