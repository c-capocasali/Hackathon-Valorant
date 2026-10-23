# Valorant Virtual Coach

Assistente tatico virtual para Valorant. Processa telemetria e economia de
partidas e cruza com uma base global de partidas de alto nivel para gerar
insights acionaveis durante a Fase de Compra (Buy Phase) e um resumo analitico
ao final do jogo.

## Visao Geral

O sistema le os arquivos JSON do desafio
(https://github.com/c-capocasali/Hackathon-Valorant - formato oficial
Riot/Valorant) e:

1. Agrega toda a base global de campeonatos em um cache Parquet (leitura
   rapida, RNF03).
2. Treina um modelo XGBoost para prever a probabilidade de vitoria do time no
   round (RF07).
3. Roda um simulador (MatchSimulator) que "libera" um round por vez a cada N
   segundos para testar a reatividade da interface.
4. Exibe as dicas em um overlay transparente (PySide6) ou, em caso de bloqueio
   pelo anti-cheat, em uma interface web alternativa (RNF02).

## Mapeamento de Requisitos

| Req | Descricao | Onde |
|-----|-----------|------|
| RF01 | Modulo de abertura (composicao inicial) | data_engine.opening_advice |
| RF02 | Assistente de economia/loja (Eco/Half/Full) | data_engine.economy_advice |
| RF03 | Posicionamento da Spike | data_engine.spike_recommendation |
| RF04 | Zonas de perigo (heatmaps) | data_engine.danger_zones |
| RF05 | Avaliacao de precisao (HS%) | data_engine.aim_adjustment |
| RF06 | Consciencia espacial / mira | data_engine.spatial_advice |
| RF07 | Probabilidade de vitoria (XGBoost) | data_engine.train_win_model |
| RF08 | Dashboard pos-partida | dashboard.py + match_summary |
| RNF01 | Overlay frameless/translucido/mouse-passthrough | overlay_ui.CoachOverlay |
| RNF02 | Fallback de interface (web) | fallback_web.py |
| RNF03 | Baixa latencia (parquet, <2s) | data_engine (cache) |
| RNF04 | Sincronizacao do HUD (so na buy phase) | overlay_ui (maquina de estados) |
| RN01 | Economia prioriza o meta | _best_loadout (winrate global) |
| RN02 | Dicas mecanicas so com desvio relevante | aim_adjustment (<15% HS) |
| RN03 | Sem API do Valorant | usa so os JSON + tabelas estaticas |

## Estrutura de Diretorios

    main.py                  # ponto de entrada (GUI / console / web)
    src/
      data_engine.py         # processamento Pandas + agregacoes + modelo
      simulator.py           # MatchSimulator (mock)
      overlay_ui.py          # janela transparente + maquina de estados
      dashboard.py           # dashboard pos-partida (matplotlib)
      fallback_web.py        # interface web alternativa (RNF02)
      game_data.py           # tabelas estaticas (UUID -> nome, custos)
    data/
      matches/               # base global de campeonatos (JSON)
      live_match.json        # partida atual (simulada)
      matches/_cache/        # parquet + modelo treinado (gerado)
    tests/                   # pytest (10 testes)

## Esquema de Dados (formato real)

Cada arquivo JSON tem as chaves principais do desafio:

    matchInfo { mapId, matchId, ... }
    players   [ { puuid, teamId, characterId, gameName, ... } ]
    teams     [ { teamId, won, roundsWon, ... } ]
    roundResults [ {
        roundNum, roundResult, winningTeam, winningTeamRole,
        plantSite, plantLocation {x,y},
        playerStats [ {
            economy { loadoutValue, weapon, armor, remaining, spent },
            damage  [ { receiver, damage, legshots, bodyshots, headshots } ],
            kills   [ { killer, victim, victimLocation {x,y},
                        playerLocations [ { puuid, viewRadians, location {x,y} } ] } ]
        } ]
    } ]

Mapeamentos criticos do desafio:

- Economia: roundResults[i].playerStats[j].economy
- Mira/Dano: roundResults[i].playerStats[j].damage
- Telemetria: roundResults[i].playerStats[j].kills[].playerLocations
  (campos x, y, viewRadians)

Nota: "remaining" no formato Riot e o saldo pos-compra; o saldo disponivel para
a buy phase e calculado como remaining + spent.

## Instalacao

    python3 -m venv --system-site-packages .venv
    source .venv/bin/activate
    pip install -r requirements.txt

## Uso

    # overlay PyQt (principal)
    python main.py

    # fallback console (headless / sem display)
    python main.py --mode console

    # fallback web (segundo monitor / celular) - RNF02
    python main.py --mode web --port 8080

    # partida especifica
    python main.py --match data/live_match.json

## Testes

    python -m pytest tests/ -q

## Conformidade RN03

O sistema nao consulta a API do Valorant nem nenhum servico externo em tempo de
execucao. Todos os dados de partida vem dos arquivos JSON do repositorio. As
tabelas de UUID -> nome (agentes, armas, armaduras, mapas) sao metadados
estaticos do manifesto publico do jogo, embutidos como constantes em
game_data.py apenas para traduzir os IDs opacos dos JSONs em nomes legiveis.
