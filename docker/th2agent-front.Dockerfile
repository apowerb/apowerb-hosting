# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# th2agent-front — le noyau open core (interface Next.js)
#
# `API_URL` est lue au *build* comme a l'execution : Next l'inline dans le
# bundle client pour les variables `NEXT_PUBLIC_*`. Changer l'URL de l'API
# apres coup impose donc de reconstruire l'image — c'est une contrainte de
# Next, pas un choix.
# ---------------------------------------------------------------------------

FROM node:22-slim AS deps

WORKDIR /app
COPY package.json package-lock.json ./
# `npm ci` et pas `npm install` : il respecte le lock au bit pres, donc deux
# constructions de la meme reference donnent les memes dependances.
RUN npm ci


FROM node:22-slim AS build

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG API_URL=http://th2agent:8000
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV API_URL=$API_URL NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build


FROM node:22-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

# Next `start` a besoin du build, du manifeste et des dependances de
# production. On ne copie pas le reste des sources : l'image sert a executer,
# pas a developper.
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.mjs ./next.config.mjs
COPY --from=build /app/messages ./messages

RUN useradd --create-home --uid 10002 th2front && chown -R th2front:th2front /app
USER th2front

EXPOSE 3000
# Sonde en Node plutot qu'avec curl : aucun paquet systeme a installer pour
# une requete HTTP que le runtime deja present sait faire. La construction ne
# depend ainsi d'aucun miroir Debian.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/', r => process.exit(r.statusCode < 500 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["npm", "run", "start"]
