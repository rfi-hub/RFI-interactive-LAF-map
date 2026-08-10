(() => {
  let mapSequence = 0;
  const colorFor = (id) => `hsl(${[...id].reduce((a, c) => a + c.charCodeAt(0), 0) % 360} 62% 39%)`;
  const hashFor = (value) => [...String(value)].reduce((total, character) => (total * 31 + character.charCodeAt(0)) >>> 0, 17);
  const layerClassFor = layer => `rfi-layer-${String(layer?.id || layer?.name || 'feature').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`;
  const landuseSymbol = (source) => {
    const properties = source?.properties || source || {};
    const name = String(properties['Land-use parcel'] || source?.name || 'Land-use parcel');
    const id = String(properties._rfi_source_id || source?.id || name);
    if (/^syntropic\b/i.test(name)) return {color: '#5d9e5b', pattern: 'diagonal', key: 'syntropic'};
    const colours = ['#cc6b5a', '#b79a45', '#4f9ba9', '#9a6ba4', '#718c52', '#c9834f', '#6d83b6', '#9a7060'];
    const patterns = ['solid', 'diagonal', 'crosshatch', 'dots'];
    const hash = hashFor(id);
    return {color: colours[hash % colours.length], pattern: patterns[Math.floor(hash / colours.length) % patterns.length], key: id};
  };
  const landusePreviewFill = (symbol) => {
    const hatch = 'rgba(20, 38, 26, .72)';
    if (symbol.pattern === 'diagonal') return `repeating-linear-gradient(135deg, transparent 0 6px, ${hatch} 6px 7px), ${symbol.color}`;
    if (symbol.pattern === 'crosshatch') return `repeating-linear-gradient(135deg, transparent 0 6px, ${hatch} 6px 7px), repeating-linear-gradient(45deg, transparent 0 6px, ${hatch} 6px 7px), ${symbol.color}`;
    if (symbol.pattern === 'dots') return `radial-gradient(${hatch} 1px, transparent 1.2px), ${symbol.color}`;
    return symbol.color;
  };
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const capitalizeFirstLetter = value => String(value ?? '').replace(/[A-Za-z]/, character => character.toUpperCase());
  const propertyValue = (properties, names) => {
    const entries = Object.entries(properties || {});
    for (const name of names) {
      const match = entries.find(([key]) => key.trim().toLocaleLowerCase() === name.toLocaleLowerCase());
      if (match && match[1] != null && String(match[1]).trim() !== '') return String(match[1]).trim();
    }
    return '';
  };
  const cssColour = (value, fallback = '#718c52') => {
    const colour = String(value || '').trim();
    return /^#[\da-f]{3,8}$/i.test(colour) || /^(?:rgb|hsl)a?\([\d\s.,%+-]+\)$/i.test(colour) ? colour : fallback;
  };
  const qgisLinePatternPreview = style => {
    const angle = Number.isFinite(Number(style.pattern_angle)) ? Number(style.pattern_angle) : 135;
    const spacing = Math.max(2, Number(style.pattern_spacing_px) || 7.56);
    const width = Math.max(.5, Number(style.pattern_width_px) || 1.13);
    const gap = spacing - width;
    const colour = cssColour(style.pattern_color, '#007cff');
    const hatch = direction => `repeating-linear-gradient(${direction}deg, transparent 0 ${gap}px, ${colour} 0 ${spacing}px)`;
    return style.pattern_crosshatch ? `${hatch(angle)}, ${hatch(angle + 90)}` : hatch(angle);
  };
  const ringAreaSquareMetres = (coordinates) => {
    if (!Array.isArray(coordinates) || coordinates.length < 4) return 0;
    const ring = coordinates.slice();
    const first = ring[0];
    const last = ring.at(-1);
    if (first?.[0] === last?.[0] && first?.[1] === last?.[1]) ring.pop();
    const validRing = ring.filter(point => Array.isArray(point) && Number.isFinite(Number(point[0])) && Number.isFinite(Number(point[1])));
    if (validRing.length < 3) return 0;
    const radians = Math.PI / 180;
    const semiMajorAxisMetres = 6378137;
    const eccentricitySquared = 6.69437999014e-3;
    const unwrappedLongitudes = [];
    validRing.forEach((point, index) => {
      let longitude = Number(point[0]);
      if (index) {
        const previousLongitude = unwrappedLongitudes[index - 1];
        while (longitude - previousLongitude > 180) longitude -= 360;
        while (longitude - previousLongitude < -180) longitude += 360;
      }
      unwrappedLongitudes.push(longitude);
    });
    const referenceLatitude = validRing.reduce((total, point) => total + Number(point[1]), 0) / validRing.length * radians;
    const referenceLongitude = unwrappedLongitudes.reduce((total, longitude) => total + longitude, 0) / unwrappedLongitudes.length * radians;
    const sinLatitude = Math.sin(referenceLatitude);
    const radiusDenominator = Math.sqrt(1 - eccentricitySquared * sinLatitude * sinLatitude);
    const primeVerticalRadius = semiMajorAxisMetres / radiusDenominator;
    const meridionalRadius = semiMajorAxisMetres * (1 - eccentricitySquared) / (radiusDenominator ** 3);
    const projected = validRing.map((point, index) => ({
      x: (unwrappedLongitudes[index] * radians - referenceLongitude) * primeVerticalRadius * Math.cos(referenceLatitude),
      y: (Number(point[1]) * radians - referenceLatitude) * meridionalRadius,
    }));
    let doubleArea = 0;
    for (let index = 0; index < projected.length; index += 1) {
      const current = projected[index];
      const next = projected[(index + 1) % projected.length];
      doubleArea += current.x * next.y - next.x * current.y;
    }
    return doubleArea / 2;
  };
  const geometryAreaHectares = (geometry) => {
    const polygonAreaSquareMetres = coordinates => {
      if (!Array.isArray(coordinates) || !coordinates.length) return 0;
      const outerArea = Math.abs(ringAreaSquareMetres(coordinates[0]));
      const holesArea = coordinates.slice(1).reduce((total, ring) => total + Math.abs(ringAreaSquareMetres(ring)), 0);
      return Math.max(0, outerArea - holesArea);
    };
    if (geometry?.type === 'Polygon') return polygonAreaSquareMetres(geometry.coordinates) / 10000;
    if (geometry?.type === 'MultiPolygon') return geometry.coordinates.reduce((total, polygon) => total + polygonAreaSquareMetres(polygon), 0) / 10000;
    return null;
  };
  const formatHectares = hectares => Number.isFinite(hectares)
    ? `${new Intl.NumberFormat('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(hectares)} ha`
    : '';
  const censusStrata = [
    {key: 'emergent', label: 'Emergent', colour: '#bd6b4f'},
    {key: 'high', label: 'High', colour: '#dfb24a'},
    {key: 'medium', label: 'Medium', colour: '#78927c'},
    {key: 'low', label: 'Low', colour: '#987db7'},
  ];
  const parsePlantCensus = value => {
    const rows = String(value || '').split(/\r?\n/).map(line => {
      const [rawName, ...rawCount] = line.split(/\t+/);
      const name = String(rawName || '').trim();
      const countText = rawCount.join('').trim().replace(/,/g, '');
      const count = countText === '' ? 0 : Number(countText);
      return name && Number.isFinite(count) && count > 0 ? {name, count: Math.round(count)} : null;
    }).filter(Boolean);
    const total = rows.reduce((sum, row) => sum + row.count, 0);
    return {total, rows: rows.map(row => ({...row, percentage: total ? row.count / total * 100 : 0}))};
  };
  const summarizeCensusStrata = (census, configuredMapping = {}) => {
    const mapping = new Map(Object.entries(configuredMapping).map(([name, details]) => [name.trim().toLocaleLowerCase(), details]));
    const rows = censusStrata.map(stratum => ({...stratum, count: 0, percentage: 0}));
    const rowByKey = new Map(rows.map(row => [row.key, row]));
    census.rows.forEach(tree => {
      const configured = mapping.get(tree.name.trim().toLocaleLowerCase());
      const display = typeof configured === 'string' ? configured : configured?.display;
      const key = String(display || '').trim().toLocaleLowerCase();
      if (rowByKey.has(key)) rowByKey.get(key).count += tree.count;
    });
    const classifiedTotal = rows.reduce((total, row) => total + row.count, 0);
    rows.forEach(row => { row.percentage = classifiedTotal ? row.count / classifiedTotal * 100 : 0; });
    return {total: classifiedTotal, rows};
  };
  const censusPieGradient = strata => {
    if (!strata.total) return '#dfe5e0 0 100%';
    let cumulative = 0;
    return strata.rows.filter(row => row.count > 0).map(row => {
      const start = cumulative / strata.total * 100;
      cumulative += row.count;
      const end = cumulative / strata.total * 100;
      return `${row.colour} ${start.toFixed(3)}% ${end.toFixed(3)}%`;
    }).join(', ');
  };
  const formatCensusPercentage = percentage => percentage > 0 && percentage < .1 ? '<0.1%' : `${percentage.toFixed(1)}%`;
  const buildParcelPopup = (layer, feature, resolveUrl) => {
    const properties = feature?.properties || {};
    const popupOptions = layer.popup || {};
    const seed = hashFor(`${layer.id || layer.name || 'parcel'}:${JSON.stringify(properties)}`);
    const placeholderId = `PX-${(seed % 0xffff).toString(16).toUpperCase().padStart(4, '0')}`;
    const title = capitalizeFirstLetter(popupOptions.title || propertyValue(properties, ['Name', 'Land-use parcel', 'Title']) || `Parcel ${placeholderId}`);
    const description = capitalizeFirstLetter(popupOptions.description || propertyValue(properties, ['Landuse description', 'Land use description', 'Description', 'Insights', 'Usage'])
      || 'No land-use description has been entered for this parcel.');
    const history = capitalizeFirstLetter(propertyValue(properties, ['Past use history', 'Past usage', 'Past use', 'History'])
      || 'No past-use history has been entered for this parcel.');
    const date = propertyValue(properties, ['Date created', 'Date Created', 'Date planted', 'Date added', 'Date'])
      || '-';
    const calculatedAreaHectares = geometryAreaHectares(feature?.geometry);
    const area = formatHectares(calculatedAreaHectares) || propertyValue(properties, ['Area', 'Area ']) || '0.00 ha';
    const currentUse = propertyValue(properties, ['Current use', 'Land use', 'Land-use parcel']) || layer.name || `Usus ${(seed % 90) + 10}`;
    const layerSymbol = layer.style?.kind === 'landuse-parcels' ? landuseSymbol(feature) : null;
    const isSyntropic = layerSymbol?.key === 'syntropic' || /^syntropic\b/i.test(currentUse) || /^syntropic\b/i.test(layer.name || '');
    const plantCensus = parsePlantCensus(propertyValue(properties, ['Plant census', 'Plant Census']));
    const strataSummary = summarizeCensusStrata(plantCensus, popupOptions.census_strata_by_species);
    const showCompositionChart = isSyntropic && strataSummary.total > 0;
    const symbolColour = cssColour(layerSymbol?.color || layer.style?.fill_color || layer.style?.color);
    const mediaPropertyName = propertyValue(properties, ['Name', 'Land-use parcel', 'Title']);
    const hideMediaNames = Array.isArray(popupOptions.hide_media_by_name) ? popupOptions.hide_media_by_name : [];
    const hideMedia = popupOptions.hide_media === true || hideMediaNames.some(name =>
      String(name).toLowerCase() === String(mediaPropertyName || '').toLowerCase()
    );
    const hideHistoryNames = Array.isArray(popupOptions.hide_history_by_name) ? popupOptions.hide_history_by_name : [];
    const hideHistory = popupOptions.hide_history === true || hideHistoryNames.some(name =>
      String(name).toLowerCase() === String(mediaPropertyName || '').toLowerCase()
    );
    const mappedMediaKey = Object.keys(popupOptions.media_by_name || {}).find(key => key.toLowerCase() === String(mediaPropertyName || '').toLowerCase());
    const indexedMedia = popupOptions.media_by_feature_index?.[String(properties._rfi_feature_index || '')];
    const mappedMedia = Array.isArray(indexedMedia)
      ? indexedMedia
      : mappedMediaKey ? popupOptions.media_by_name[mappedMediaKey] : [];
    const embeddedMedia = Array.isArray(properties._rfi_media) ? properties._rfi_media : [];
    const configuredMediaSource = [
      ...(Array.isArray(mappedMedia) ? mappedMedia : []),
      ...embeddedMedia,
    ];
    const configuredMedia = configuredMediaSource
      .filter(item => item && item.type === 'image' && typeof item.url === 'string' && item.url.trim())
      .filter((item, index, items) => items.findIndex(candidate => candidate.url === item.url) === index);
    const resolvedMedia = configuredMedia.map(item => ({
      name: item.name || title,
      alt: item.alt || `${title} photograph`,
      url: typeof resolveUrl === 'function' ? resolveUrl(item.url) : item.url,
    }));
    const firstMedia = resolvedMedia[0];
    const firstMediaUrl = firstMedia?.url || '';
    const mediaPanel = hideMedia ? '' : firstMediaUrl
      ? `<div class="rfi-parcel-popup__media rfi-parcel-popup__media--image" data-media-mode="image" data-index="0" data-media-items="${escapeHtml(JSON.stringify(resolvedMedia))}" aria-label="${escapeHtml(firstMedia.alt)}">
          <img class="rfi-parcel-popup__media-image" src="${escapeHtml(firstMediaUrl)}" alt="${escapeHtml(firstMedia.alt)}" decoding="async">
          <span class="rfi-parcel-popup__media-type">Image</span>
          ${resolvedMedia.length > 1 ? '<button type="button" class="rfi-parcel-popup__media-control rfi-parcel-popup__media-control--previous" data-direction="-1" aria-label="Previous parcel image">&lsaquo;</button><button type="button" class="rfi-parcel-popup__media-control rfi-parcel-popup__media-control--next" data-direction="1" aria-label="Next parcel image">&rsaquo;</button>' : ''}
          <span class="rfi-parcel-popup__media-count">1 / ${resolvedMedia.length}</span>
        </div>`
      : `<div class="rfi-parcel-popup__media rfi-parcel-popup__media--empty" aria-label="No image available for this parcel">
          <div class="rfi-parcel-popup__media-grid" aria-hidden="true"></div>
          <span class="rfi-parcel-popup__media-type">No image available</span>
          <strong class="rfi-parcel-popup__media-name">No matching photograph has been added for this parcel.</strong>
        </div>`;
    const censusRows = plantCensus.rows.map(row => `
                <tr><td>${escapeHtml(row.name)}</td><td>${new Intl.NumberFormat('en-US').format(row.count)}</td><td>${escapeHtml(formatCensusPercentage(row.percentage))}</td></tr>`).join('');
    const strataRows = strataSummary.rows.map(row => `
              <li><i style="--rfi-stratum-colour:${row.colour}"></i><span>${escapeHtml(row.label)}</span><b>${new Intl.NumberFormat('en-US').format(row.count)}</b><em>${escapeHtml(formatCensusPercentage(row.percentage))}</em></li>`).join('');
    const syntropicComposition = `
          ${showCompositionChart ? `<div class="rfi-parcel-popup__pie-group"><div class="rfi-parcel-popup__pie" style="background:conic-gradient(${censusPieGradient(strataSummary)})" role="img" aria-label="Tree census strata for ${escapeHtml(title)}; ${new Intl.NumberFormat('en-US').format(strataSummary.total)} classified trees"></div><p class="rfi-parcel-popup__pie-total"><b>${new Intl.NumberFormat('en-US').format(strataSummary.total)}</b> trees</p></div>` : ''}
          <div class="rfi-parcel-popup__composition-copy">
            <h3 id="${escapeHtml(placeholderId)}-composition">Composition</h3>
            <strong>${escapeHtml(currentUse)}</strong>
            ${plantCensus.total ? `
              <p class="rfi-parcel-popup__census-label">Composition by tree stratum</p>
              <ul class="rfi-parcel-popup__strata" aria-label="Tree strata counts and percentages">${strataRows}</ul>` : '<p class="rfi-parcel-popup__census-empty">No plant census has been entered for this parcel.</p>'}
          </div>`;
    const fullCensus = plantCensus.total ? `
          <details class="rfi-parcel-popup__census-details">
            <summary>See full tree census</summary>
            <div class="rfi-parcel-popup__census-scroll">
              <table class="rfi-parcel-popup__census-table">
                <thead><tr><th scope="col">Tree type</th><th scope="col">Total count</th><th scope="col">Percentage of total trees</th></tr></thead>
                <tbody>${censusRows}</tbody>
              </table>
            </div>
          </details>` : '';
    const compositionPanel = isSyntropic && !popupOptions.hide_composition ? `
        <section class="rfi-parcel-popup__composition${showCompositionChart ? '' : ' rfi-parcel-popup__composition--without-chart'}${isSyntropic ? ' rfi-parcel-popup__composition--census' : ''}" aria-labelledby="${escapeHtml(placeholderId)}-composition">
          ${syntropicComposition}
          ${fullCensus}
        </section>` : '';
    const historyPanel = hideHistory ? '' : `
        <section class="rfi-parcel-popup__history">
          <h3>Past use history</h3>
          <p>${escapeHtml(history)}</p>
        </section>`;
    return `
      <article class="rfi-parcel-popup" style="--rfi-parcel-symbol:${symbolColour}">
        <div class="rfi-parcel-popup__hero${hideMedia ? ' rfi-parcel-popup__hero--without-media' : ''}">
          ${mediaPanel}
          <div class="rfi-parcel-popup__introduction">
            <h2>${escapeHtml(title)}</h2>
            <p>${escapeHtml(description)}</p>
            <dl class="rfi-parcel-popup__meta"><div><dt>Date</dt><dd>${escapeHtml(date)}</dd></div><div><dt>Area</dt><dd data-rfi-area-hectares="${Number.isFinite(calculatedAreaHectares) ? calculatedAreaHectares.toFixed(6) : ''}" title="Calculated from parcel polygon geometry on WGS 84">${escapeHtml(area)}</dd></div></dl>
          </div>
        </div>
        ${compositionPanel}
        ${historyPanel}
      </article>`;
  };
  const wireParcelPopup = (popup) => {
    const media = popup.getElement()?.querySelector('.rfi-parcel-popup__media');
    if (!media || media.dataset.rfiWired === 'true') return;
    media.dataset.rfiWired = 'true';
    const stopMapPropagation = event => event.stopPropagation();
    L.DomEvent.disableClickPropagation(media);
    L.DomEvent.disableScrollPropagation(media);
    if (media.dataset.mediaMode === 'image') {
      let items = [];
      try { items = JSON.parse(media.dataset.mediaItems || '[]'); } catch { items = []; }
      const image = media.querySelector('.rfi-parcel-popup__media-image');
      const count = media.querySelector('.rfi-parcel-popup__media-count');
      if (!image || !items.length) return;
      const showImage = index => {
        const item = items[index];
        media.dataset.index = String(index);
        image.src = item.url;
        image.alt = item.alt;
        media.setAttribute('aria-label', item.alt);
        if (count) count.textContent = `${index + 1} / ${items.length}`;
      };
      media.querySelectorAll('.rfi-parcel-popup__media-control').forEach(button => {
        button.addEventListener('pointerdown', stopMapPropagation);
        button.addEventListener('click', event => {
          event.preventDefault();
          stopMapPropagation(event);
          const nextIndex = (Number(media.dataset.index || 0) + Number(button.dataset.direction) + items.length) % items.length;
          showImage(nextIndex);
        });
      });
      return;
    }
    const names = ['Imago 01', 'Video 02', 'IR 03'];
    const name = media.querySelector('.rfi-parcel-popup__media-name');
    const count = media.querySelector('.rfi-parcel-popup__media-count');
    media.querySelectorAll('.rfi-parcel-popup__media-control').forEach(button => {
      button.addEventListener('pointerdown', stopMapPropagation);
      button.addEventListener('click', event => {
        event.preventDefault();
        stopMapPropagation(event);
        const nextIndex = (Number(media.dataset.index || 0) + Number(button.dataset.direction) + names.length) % names.length;
        media.dataset.index = String(nextIndex);
        name.textContent = names[nextIndex];
        count.textContent = `${nextIndex + 1} / ${names.length}`;
      });
    });
  };
  const positionParcelPopup = (map, popup) => {
    if (!window.matchMedia('(min-width: 701px)').matches) return;
    const popupElement = popup?.getElement?.();
    const popupPane = popupElement?.parentElement;
    if (!popupElement || !popupPane) return;
    const mapBounds = map.getContainer().getBoundingClientRect();
    const paneBounds = popupPane.getBoundingClientRect();
    const panelLeft = mapBounds.left + mapBounds.width / 2 + 7;
    const panelBottom = 14;
    const panelTopClearance = 72;
    const maximumHeight = Math.max(280, mapBounds.height - panelTopClearance - panelBottom);
    popupElement.style.setProperty('--rfi-popup-left', `${panelLeft - paneBounds.left}px`);
    popupElement.style.setProperty('--rfi-popup-width', `${Math.max(300, mapBounds.right - 14 - panelLeft)}px`);
    popupElement.style.setProperty('--rfi-popup-max-height', `${maximumHeight}px`);
    popupElement.style.setProperty('--rfi-popup-top', '0px');
    const popupHeight = Math.min(popupElement.getBoundingClientRect().height, maximumHeight);
    const panelTop = mapBounds.bottom - panelBottom - popupHeight;
    popupElement.style.setProperty('--rfi-popup-top', `${panelTop - paneBounds.top}px`);
    popupElement.style.removeProperty('--rfi-popup-bottom');
    popupElement.style.removeProperty('--rfi-popup-height');
  };
  const interpolateColour = (colours, position) => {
    const index = Math.min(colours.length - 2, Math.max(0, Math.floor(position * (colours.length - 1))));
    const fraction = position * (colours.length - 1) - index;
    const parse = colour => [1, 3, 5].map(offset => parseInt(colour.slice(offset, offset + 2), 16));
    const start = parse(colours[index]), end = parse(colours[index + 1]);
    return `#${start.map((value, channel) => Math.round(value + (end[channel] - value) * fraction).toString(16).padStart(2, '0')).join('')}`;
  };
  const vectorStyle = (layer, feature, patternFill) => {
    if (layer.style?.kind === 'monkey-transects') {
      const transectName = String(propertyValue(feature.properties, ['title', 'Transect']) || '').trim();
      const configuredColour = layer.style.feature_colors?.[transectName];
      return {
        color: cssColour(
          configuredColour,
          cssColour(
            layer.style.color_field ? feature.properties?.[layer.style.color_field] : layer.style.color,
            cssColour(layer.style.color, layer.style.fallback_color || '#fab519')
          )
        ),
        weight: (layer.style.weight ?? .983) * (layer.style.display_width_multiplier ?? 1),
        opacity: layer.style.opacity ?? .95,
        lineCap: layer.style.line_cap || 'square',
        lineJoin: layer.style.line_join || 'bevel',
        bubblingMouseEvents: false,
        className: 'rfi-monkey-transect'
      };
    }
    if (layer.style?.kind === 'flow-channels') return {color: feature.properties?.mapped_river_nearby ? '#1261a0' : '#e88936', weight: 2.2, opacity: .9};
    if (layer.style?.kind === 'river-network-portions') {
      const basis = feature.properties?.river_network_match || '';
      return {color: basis.startsWith('Both') ? '#164d80' : basis.startsWith('Mapped') ? '#1475a3' : '#55a3b9', weight: 5, opacity: .95, lineCap: 'round'};
    }
    if (layer.style?.kind === 'watershed-rivers') return {
      color: cssColour(layer.style.color, '#00d4ff'),
      weight: layer.style.weight ?? 3.2,
      opacity: layer.style.opacity ?? 1,
      lineCap: layer.style.line_cap || 'round',
      lineJoin: layer.style.line_join || 'round',
      className: 'rfi-watershed-river'
    };
    if (layer.style?.kind === 'boundary') return {
      className: 'rfi-primary-boundary-feature',
      color: layer.style.color || '#bd332b',
      weight: layer.style.weight ?? 2.4,
      opacity: layer.style.opacity ?? 1,
      fill: false,
      lineCap: layer.style.line_cap || 'round',
      lineJoin: layer.style.line_join || 'round',
      dashArray: layer.style.dash_array || null,
    };
    if (layer.style?.kind === 'qgis-polygon') return {
      className: `rfi-landuse-feature ${layerClassFor(layer)}`,
      color: layer.style.outline_color || '#232323',
      weight: layer.style.weight ?? 1.2,
      opacity: layer.style.opacity ?? 1,
      fillColor: layer.style.fill_color || colorFor(layer.id),
      fillOpacity: layer.style.fill_opacity ?? .58,
    };
    if (layer.style?.kind === 'qgis-line-pattern-fill') return {
      className: `rfi-landuse-feature rfi-pattern-overlay-feature ${layerClassFor(layer)}`,
      color: cssColour(layer.style.outline_color, '#007cff'),
      weight: layer.style.weight ?? 1.13,
      opacity: layer.style.opacity ?? 1,
      dashArray: layer.style.outline_dash_array || null,
      fillColor: patternFill ? patternFill(layer.style) : 'transparent',
      fillOpacity: layer.style.fill_opacity ?? .75,
      lineCap: layer.style.line_cap || 'square',
      lineJoin: layer.style.line_join || 'bevel',
    };
    if (layer.style?.kind === 'landuse') { const color = colorFor(layer.id); return {className: 'rfi-landuse-feature', color, weight: 1.5, opacity: .95, fillColor: color, fillOpacity: .42}; }
    if (layer.style?.kind === 'landuse-parcels') { const symbol = landuseSymbol(feature); return {className: 'rfi-landuse-feature', color: symbol.color, weight: 1.5, opacity: .95, fillColor: patternFill ? patternFill(symbol) : symbol.color, fillOpacity: .55}; }
    if (layer.style?.kind !== 'elevation-bands') return {color: colorFor(layer.id), weight: 2, fillOpacity: .18};
    const value = Number(feature.properties?.[layer.style.field]);
    const position = Math.min(1, Math.max(0, (value - layer.style.min) / (layer.style.max - layer.style.min)));
    return {
      color: layer.style.outline_color || '#232323',
      weight: layer.style.weight ?? .98,
      opacity: layer.style.opacity ?? 1,
      fillColor: interpolateColour(layer.style.colours, position),
      fillOpacity: layer.style.fill_opacity ?? 1,
      lineJoin: layer.style.line_join || 'bevel',
    };
  };
  const createMonkeyHeatLayer = (data, style = {}) => {
    const points = (data.features || [])
      .filter(feature => feature.geometry?.type === 'Point' && feature.geometry.coordinates?.length >= 2)
      .map(feature => L.latLng(Number(feature.geometry.coordinates[1]), Number(feature.geometry.coordinates[0])))
      .filter(latlng => Number.isFinite(latlng.lat) && Number.isFinite(latlng.lng));
    const bounds = L.latLngBounds(points);
    const colours = Array.isArray(style.colours) && style.colours.length > 1
      ? style.colours.map(colour => cssColour(colour, '#fff5f0'))
      : ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#a50f15', '#67000d'];
    const alphaStops = Array.isArray(style.colour_alphas) && style.colour_alphas.length === colours.length
      ? style.colour_alphas.map(value => Math.min(255, Math.max(0, Number(value) || 0)))
      : [0, 166, 255, 255, 255, 255, 255, 255, 255];
    const palette = new Uint8ClampedArray(256 * 3);
    const paletteAlpha = new Uint8ClampedArray(256);
    for (let value = 0; value < 256; value += 1) {
      const colour = interpolateColour(colours, value / 255);
      palette[value * 3] = parseInt(colour.slice(1, 3), 16);
      palette[value * 3 + 1] = parseInt(colour.slice(3, 5), 16);
      palette[value * 3 + 2] = parseInt(colour.slice(5, 7), 16);
      const alphaPosition = value / 255 * (alphaStops.length - 1);
      const alphaIndex = Math.min(alphaStops.length - 2, Math.floor(alphaPosition));
      const alphaFraction = alphaPosition - alphaIndex;
      paletteAlpha[value] = Math.round(alphaStops[alphaIndex] + (alphaStops[alphaIndex + 1] - alphaStops[alphaIndex]) * alphaFraction);
    }
    const radius = Math.max(12, Number(style.radius) || 38);
    const pointAlpha = Math.min(.5, Math.max(.04, Number(style.point_alpha) || .18));
    const configuredMaximum = Number(style.max_intensity);
    const maxIntensity = Number.isFinite(configuredMaximum) && configuredMaximum > 0
      ? Math.min(1, Math.max(.05, configuredMaximum))
      : null;
    const opacity = Math.min(1, Math.max(.1, Number(style.opacity) || 1));
    const paneName = 'rfiMonkeyHeatPane';
    const HeatLayer = L.Layer.extend({
      onAdd(map) {
        this._map = map;
        let pane = map.getPane(paneName);
        if (!pane) {
          pane = map.createPane(paneName, map.getPane('overlayPane')?.parentNode);
          pane.style.zIndex = '390';
          pane.style.pointerEvents = 'none';
        }
        this._canvas = L.DomUtil.create('canvas', 'leaflet-layer rfi-monkey-heatmap', pane);
        this._canvas.setAttribute('role', 'img');
        this._canvas.setAttribute('aria-label', `Density heatmap calculated from ${points.length} howler monkey sighting locations`);
        this._intensityCanvas = document.createElement('canvas');
        map.on('moveend zoomend resize rotate', this._scheduleDraw, this);
        this._scheduleDraw();
      },
      onRemove(map) {
        map.off('moveend zoomend resize rotate', this._scheduleDraw, this);
        if (this._frame) cancelAnimationFrame(this._frame);
        this._canvas?.remove();
        this._canvas = null;
        this._intensityCanvas = null;
        this._map = null;
      },
      getBounds() { return bounds; },
      _scheduleDraw() {
        if (this._frame) cancelAnimationFrame(this._frame);
        this._frame = requestAnimationFrame(() => { this._frame = 0; this._draw(); });
      },
      _draw() {
        if (!this._map || !this._canvas || !this._intensityCanvas) return;
        const size = this._map.getSize();
        const pixelRatio = Math.min(2, window.devicePixelRatio || 1);
        const width = Math.max(1, Math.round(size.x * pixelRatio));
        const height = Math.max(1, Math.round(size.y * pixelRatio));
        this._canvas.width = width;
        this._canvas.height = height;
        this._canvas.style.width = `${size.x}px`;
        this._canvas.style.height = `${size.y}px`;
        this._intensityCanvas.width = width;
        this._intensityCanvas.height = height;
        L.DomUtil.setPosition(this._canvas, this._map.containerPointToLayerPoint([0, 0]));

        const intensityContext = this._intensityCanvas.getContext('2d', {willReadFrequently: true});
        intensityContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        intensityContext.clearRect(0, 0, size.x, size.y);
        intensityContext.globalCompositeOperation = 'lighter';
        points.forEach(latlng => {
          const point = this._map.latLngToContainerPoint(latlng);
          const gradient = intensityContext.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
          gradient.addColorStop(0, `rgba(0,0,0,${pointAlpha})`);
          gradient.addColorStop(.4, `rgba(0,0,0,${pointAlpha * .72})`);
          gradient.addColorStop(1, 'rgba(0,0,0,0)');
          intensityContext.fillStyle = gradient;
          intensityContext.fillRect(point.x - radius, point.y - radius, radius * 2, radius * 2);
        });

        const intensityImage = intensityContext.getImageData(0, 0, width, height);
        const outputContext = this._canvas.getContext('2d');
        const outputImage = outputContext.createImageData(width, height);
        let observedMaximum = 0;
        for (let index = 3; index < intensityImage.data.length; index += 4) {
          observedMaximum = Math.max(observedMaximum, intensityImage.data[index] / 255);
        }
        const normalizationMaximum = maxIntensity || observedMaximum || 1;
        for (let index = 0; index < intensityImage.data.length; index += 4) {
          const intensity = intensityImage.data[index + 3] / 255;
          if (intensity < .008) continue;
          const paletteValue = Math.round(Math.min(1, intensity / normalizationMaximum) * 255);
          const paletteIndex = paletteValue * 3;
          outputImage.data[index] = palette[paletteIndex];
          outputImage.data[index + 1] = palette[paletteIndex + 1];
          outputImage.data[index + 2] = palette[paletteIndex + 2];
          outputImage.data[index + 3] = Math.round(paletteAlpha[paletteValue] * opacity);
        }
        outputContext.putImageData(outputImage, 0, 0);
      },
    });
    return new HeatLayer();
  };
  const boot = async (root) => {
    if (root.dataset.ready === 'true') return;
    root.dataset.ready = 'true';
    const configUrl = root.dataset.configUrl || (window.RFIMapData && window.RFIMapData.configUrl);
    const configBaseUrl = new URL(configUrl, window.location.href);
    const configVersion = configBaseUrl.searchParams.get('v');
    const resolveUrl = (url) => {
      if (!url) return url;
      const resolved = new URL(url, configBaseUrl);
      if (configVersion && resolved.origin === configBaseUrl.origin && !resolved.searchParams.has('v')) {
        resolved.searchParams.set('v', configVersion);
      }
      return resolved.href;
    };
    const resolveTileUrl = (url) => resolveUrl(url)?.replace(/%7B/gi, '{').replace(/%7D/gi, '}');
    const canvas = root.querySelector('.rfi-map__canvas');
    const layerStore = root.querySelector('.rfi-map__layer-store');
    const panel = root.querySelector('.rfi-map__layers');
    const assetsPanel = root.querySelector('.rfi-map__assets');
    const status = root.querySelector('.rfi-map__status');
    const loading = root.querySelector('.rfi-map__loading');
    const sectionButtons = [...root.querySelectorAll('.rfi-map__section-tab')];
    const sectionNames = new Map(sectionButtons.map(button => [button.dataset.rfiSection, button.textContent.trim()]));
    const validSections = new Set(sectionNames.keys());
    const layerStoreId = layerStore.id || `rfi-map-layers-${++mapSequence}`;
    layerStore.id = layerStoreId;
    let activeSection = sectionButtons[0]?.dataset.rfiSection || '';
    let emptyMessage = 'No map data is connected.';
    let environmentalAnalysisControl;
    let environmentalAnalysisCount = 0;
    const emptyState = document.createElement('p'); emptyState.className = 'rfi-map__empty'; panel.append(emptyState);
    const sectionFor = entry => {
      const explicit = String(entry?.section || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      if (validSections.has(explicit)) return explicit;
      const value = [entry?.group, entry?.name, entry?.id, entry?.kind, entry?.style?.kind, entry?.metric].filter(Boolean).join(' ').toLowerCase();
      if (/monkey|primate/.test(value)) return 'monkey-study';
      if (/contour|elevation|\bdem\b|watershed|slope|terrain/.test(value)) return 'contours';
      if (/environment|health|ndvi|\bevi\b|ndmi|ndwi|reflectance|soil/.test(value)) return 'environmental-health-analysis';
      if (/land.?use|parcel|syntropic|pasture|forest|bamboo|cacao|teak/.test(value)) return 'land-use';
      return '';
    };
    const updateSectionVisibility = () => {
      const labels = [...panel.querySelectorAll('label')];
      labels.forEach(label => {
        const matchesSection = label.dataset.rfiSection === activeSection;
        label.hidden = !matchesSection;
        const input = label.querySelector('input[type="checkbox"]');
        if (input && input.checked !== matchesSection) {
          input.checked = matchesSection;
          input.dispatchEvent(new Event('change'));
        }
      });
      panel.querySelectorAll('.rfi-layer-group').forEach(group => {
        group.hidden = ![...group.querySelectorAll('label')].some(label => !label.hidden);
      });
      const analysesVisible = activeSection === 'environmental-health-analysis' && !!environmentalAnalysisControl;
      if (environmentalAnalysisControl) environmentalAnalysisControl.hidden = !analysesVisible;
      root.dispatchEvent(new CustomEvent('rfi-section-change', {detail: {section: activeSection}}));
      const visible = labels.filter(label => !label.hidden).length + (analysesVisible ? environmentalAnalysisCount : 0);
      emptyState.hidden = visible > 0;
      emptyState.textContent = activeSection
        ? `No ${sectionNames.get(activeSection)} layers are connected.`
        : emptyMessage;
      if (root.classList.contains('rfi-map--ready')) {
        status.textContent = analysesVisible
          ? `${sectionNames.get(activeSection)} · ${environmentalAnalysisCount} analyses available`
          : `${sectionNames.get(activeSection)} · ${visible} layer${visible === 1 ? '' : 's'} visible`;
      }
    };
    const setActiveSection = section => {
      if (!validSections.has(section)) return;
      activeSection = section;
      root.classList.toggle('rfi-map--landuse-active', activeSection === 'land-use');
      sectionButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.rfiSection === activeSection)));
      updateSectionVisibility();
    };
    sectionButtons.forEach(button => button.addEventListener('click', () => {
      setActiveSection(button.dataset.rfiSection);
      map.closePopup();
    }));
    setActiveSection(activeSection);
    const legendPanel = document.createElement('aside'); legendPanel.className = 'rfi-map__legend'; legendPanel.hidden = true;
    const landuseLegendPanel = document.createElement('aside'); landuseLegendPanel.className = 'rfi-map__landuse-legend'; landuseLegendPanel.hidden = true;
    landuseLegendPanel.setAttribute('aria-label', 'Land use legend');
    root.append(legendPanel, landuseLegendPanel);
    const activeLegends = new Map();
    const legendKey = entry => entry.legend?.title || entry.name;
    const layerGroups = new Map();
    const landuseLegendEntries = new Map();
    const positionLanduseLegend = () => {
      landuseLegendPanel.style.removeProperty('top');
      landuseLegendPanel.style.removeProperty('max-height');
      landuseLegendPanel.style.removeProperty('right');
      if (landuseLegendPanel.hidden || !window.matchMedia('(min-width: 701px)').matches) return;
      const popup = map?._popup;
      if (!popup?.isOpen?.()) return;
      const popupElement = popup.getElement?.();
      if (!popupElement?.classList.contains('rfi-parcel-popup-shell')) return;
      const mapBox = root.getBoundingClientRect();
      const popupBox = popupElement.getBoundingClientRect();
      landuseLegendPanel.style.right = `${Math.round(mapBox.right - popupBox.left + 10)}px`;
    };
    const positionEnvironmentalAnalysis = () => {
      if (!environmentalAnalysisControl || environmentalAnalysisControl.hidden) return;
      const mapBox = root.getBoundingClientRect();
      const legendBox = legendPanel.getBoundingClientRect();
      const legendBottom = legendPanel.hidden ? 14 : Math.max(8, mapBox.bottom - legendBox.bottom);
      const legendHeight = legendPanel.hidden ? 0 : legendBox.height + 10;
      environmentalAnalysisControl.style.bottom = `${Math.round(legendBottom + legendHeight)}px`;
    };
    const registerLanduseLegend = layer => {
      if (layer.show_in_legend === false) return;
      const kind = layer.style?.kind;
      if (sectionFor(layer) !== 'land-use' || !['qgis-polygon', 'qgis-line-pattern-fill', 'landuse', 'landuse-parcels'].includes(kind)) return;
      if (kind === 'landuse-parcels' && Array.isArray(layer.source_layers)) {
        layer.source_layers.forEach(source => {
          const symbol = landuseSymbol(source);
          landuseLegendEntries.set(source.id || source.name, {name: source.name, background: landusePreviewFill(symbol), pattern: symbol.pattern});
        });
        return;
      }
      const background = kind === 'qgis-line-pattern-fill'
        ? qgisLinePatternPreview(layer.style)
        : kind === 'qgis-polygon'
          ? (layer.style.fill_color || colorFor(layer.id))
          : colorFor(layer.id);
      landuseLegendEntries.set(layer.id || layer.name, {name: layer.name, background});
    };
    const syncLanduseLegendVisibility = () => {
      const visible = activeSection === 'land-use';
      root.classList.toggle('rfi-map--landuse-active', visible);
      landuseLegendPanel.hidden = !visible;
      landuseLegendPanel.dataset.rfiVisible = String(visible);
      return visible;
    };
    const renderLanduseLegend = () => {
      landuseLegendPanel.replaceChildren();
      const visible = syncLanduseLegendVisibility();
      if (!visible) return;
      const heading = document.createElement('h3'); heading.textContent = 'Land use groups'; landuseLegendPanel.append(heading);
      if (!landuseLegendEntries.size) {
        const loadingMessage = document.createElement('p');
        loadingMessage.className = 'rfi-map__empty'; loadingMessage.textContent = 'Land-use symbology is loading.';
        landuseLegendPanel.append(loadingMessage);
      }
      landuseLegendEntries.forEach(entry => {
        const row = document.createElement('div'); row.className = 'rfi-landuse-legend__row';
        const swatch = document.createElement('span'); swatch.className = 'rfi-landuse-legend__swatch';
        swatch.setAttribute('aria-hidden', 'true'); swatch.style.background = entry.background;
        if (entry.pattern === 'dots') swatch.style.backgroundSize = '6px 6px';
        const label = document.createElement('span'); label.textContent = entry.name;
        row.append(swatch, label); landuseLegendPanel.append(row);
      });
      positionLanduseLegend();
    };
    const placeLayerControl = (control, group, standalone = false, entry = null) => {
      control.dataset.rfiSection = sectionFor(entry);
      if (standalone) { control.classList.add('rfi-primary-boundary'); panel.prepend(control); return; }
      if (!group) { panel.append(control); return; }
      if (!layerGroups.has(group)) {
        const details = document.createElement('details'); details.className = 'rfi-layer-group'; details.open = true;
        const summary = document.createElement('summary'); summary.textContent = group; details.append(summary);
        const content = document.createElement('div'); content.className = 'rfi-layer-group__content'; details.append(content);
        details.addEventListener('toggle', () => {
          if (details.open) return;
          content.querySelectorAll('input[type="checkbox"]:checked').forEach(input => {
            input.checked = false;
            input.dispatchEvent(new Event('change'));
          });
        });
        if (group === 'Plant health indicators') {
          const boundary = panel.querySelector('.rfi-primary-boundary');
          if (boundary) panel.insertBefore(details, boundary.nextSibling);
          else panel.prepend(details);
        } else panel.append(details);
        layerGroups.set(group, content);
      }
      layerGroups.get(group).append(control);
    };
    const renderLegends = () => {
      legendPanel.replaceChildren();
      if (!activeLegends.size || !landuseLegendPanel.hidden) {
        legendPanel.hidden = true;
        positionLanduseLegend();
        positionEnvironmentalAnalysis();
        return;
      }
      legendPanel.hidden = false;
      const heading = document.createElement('h3'); heading.textContent = 'Legend'; legendPanel.append(heading);
      activeLegends.forEach((legend, name) => {
        const item = document.createElement('div'); item.className = 'rfi-legend';
        const title = document.createElement('b'); title.textContent = legend.title || name;
        if (legend.description) { title.title = legend.description; title.className = 'rfi-legend__title--help'; }
        item.append(title);
        if (Array.isArray(legend.items) && legend.items.length) {
          const list = document.createElement('div'); list.className = 'rfi-legend__items';
          legend.items.forEach(entry => {
            const row = document.createElement('div'); row.className = 'rfi-legend__item';
            const shape = entry.shape === 'line' ? 'line' : entry.shape === 'heat' ? 'heat' : 'point';
            if (shape === 'heat') row.classList.add('rfi-legend__item--heat');
            const symbol = document.createElement('span'); symbol.className = `rfi-legend__symbol rfi-legend__symbol--${shape}`;
            if (shape === 'heat') {
              const colours = Array.isArray(entry.colours) && entry.colours.length > 1 ? entry.colours : ['#fff5f0', '#fb6a4a', '#67000d'];
              symbol.style.background = `linear-gradient(to right, ${colours.map(colour => cssColour(colour, '#fff5f0')).join(', ')})`;
            } else symbol.style.setProperty('--rfi-legend-symbol', cssColour(entry.color, '#00b8c2'));
            symbol.setAttribute('aria-hidden', 'true');
            const label = document.createElement('span'); label.textContent = entry.label;
            if (shape === 'heat') {
              const labels = document.createElement('span'); labels.className = 'rfi-legend__heat-labels';
              const low = document.createElement('span'); low.textContent = entry.low_label || 'Lower density';
              const high = document.createElement('span'); high.textContent = entry.high_label || 'Higher density';
              labels.append(low, high); row.append(label, symbol, labels);
            } else row.append(symbol, label);
            list.append(row);
          });
          item.append(list); legendPanel.append(item);
          return;
        }
        const bar = document.createElement('div'); bar.className = 'rfi-legend__bar';
        bar.style.background = `linear-gradient(to right, ${legend.stops.map((stop, index) => `${stop.color} ${index / (legend.stops.length - 1) * 100}%`).join(', ')})`;
        item.append(bar);
        const values = document.createElement('div'); values.className = 'rfi-legend__values';
        legend.stops.forEach(stop => { const value = document.createElement('span'); value.textContent = stop.value; values.append(value); });
        item.append(values);
        const labels = document.createElement('div'); labels.className = 'rfi-legend__labels'; labels.textContent = `${legend.low_label}  •  ${legend.high_label}`; item.append(labels);
        legendPanel.append(item);
      });
      positionLanduseLegend();
      positionEnvironmentalAnalysis();
    };
    root.addEventListener('rfi-section-change', () => {
      renderLanduseLegend();
      renderLegends();
    });
    const map = L.map(canvas, {scrollWheelZoom: true, rotate: true, bearing: 0, shiftKeyRotate: true, touchRotate: true, rotateControl: false, zoomControl: false}).setView([0, 0], 2);
    renderLanduseLegend();
    const keepLanduseLegendVisible = () => {
      if (!syncLanduseLegendVisibility()) return;
      requestAnimationFrame(positionLanduseLegend);
    };
    map.on('zoomstart zoomanim zoom zoomend moveend', keepLanduseLegendVisible);
    L.control.zoom({position: 'bottomleft'}).addTo(map);
    let homeBounds;
    let farmBoundaryBounds;
    map.on('popupopen', event => {
      wireParcelPopup(event.popup);
      requestAnimationFrame(() => {
        positionParcelPopup(map, event.popup);
        positionLanduseLegend();
        keepLanduseLegendVisible();
      });
    });
    map.on('popupclose', () => {
      landuseLegendPanel.style.removeProperty('right');
      syncLanduseLegendVisibility();
      requestAnimationFrame(keepLanduseLegendVisible);
    });
    const repositionOpenParcelPopup = () => {
      const popup = map._popup;
      if (popup?.isOpen?.() && popup.getElement?.()?.classList.contains('rfi-parcel-popup-shell')) {
        requestAnimationFrame(() => {
          positionParcelPopup(map, popup);
          positionLanduseLegend();
        });
      }
    };
    map.on('moveend zoomend resize rotate', repositionOpenParcelPopup);
    map.on('resize', positionEnvironmentalAnalysis);
    const fitHomeBounds = () => {
      if (!homeBounds?.isValid()) return;
      map.invalidateSize({pan: false, debounceMoveend: true});
      map.fitBounds(homeBounds, {padding: [24, 24], animate: false});
    };
    const landuseRenderer = L.svg({padding: .25}); landuseRenderer.addTo(map);
    const svgNamespace = 'http://www.w3.org/2000/svg';
    const landuseDefs = document.createElementNS(svgNamespace, 'defs'); landuseRenderer._container.insertBefore(landuseDefs, landuseRenderer._container.firstChild);
    const riparianPane = map.createPane('rfiRiparianPane');
    riparianPane.style.zIndex = '350';
    const riparianRenderer = L.svg({padding: .25, pane: 'rfiRiparianPane'}); riparianRenderer.addTo(map);
    const riparianDefs = document.createElementNS(svgNamespace, 'defs'); riparianRenderer._container.insertBefore(riparianDefs, riparianRenderer._container.firstChild);
    const riparianDisplayPane = map.createPane('rfiRiparianDisplayPane', map.getPane('overlayPane')?.parentNode);
    riparianDisplayPane.style.zIndex = '410';
    riparianDisplayPane.style.pointerEvents = 'none';
    const riparianDisplayRenderer = L.svg({padding: .25, pane: 'rfiRiparianDisplayPane'}); riparianDisplayRenderer.addTo(map);
    const riparianDisplayDefs = document.createElementNS(svgNamespace, 'defs'); riparianDisplayRenderer._container.insertBefore(riparianDisplayDefs, riparianDisplayRenderer._container.firstChild);
    const qgisLinePatternFillFor = (defs, prefix, style) => {
      const colour = cssColour(style.pattern_color, '#007cff');
      const spacing = Math.max(2, Number(style.pattern_spacing_px) || 7.56);
      const width = Math.max(.5, Number(style.pattern_width_px) || 1.13);
      const angle = Number.isFinite(Number(style.pattern_angle)) ? Number(style.pattern_angle) : 135;
      const dashArray = String(style.pattern_dash_array || '').trim();
      const dashId = dashArray ? `-${dashArray.replace(/[^\d]+/g, '-')}` : '';
      const id = `${prefix}-${colour.slice(1)}-${String(spacing).replace('.', '-')}-${String(width).replace('.', '-')}-${angle}${style.pattern_crosshatch ? '-cross' : ''}${dashId}`;
      if (!defs.querySelector(`#${id}`)) {
        const pattern = document.createElementNS(svgNamespace, 'pattern');
        pattern.setAttribute('id', id);
        pattern.setAttribute('patternUnits', 'userSpaceOnUse');
        pattern.setAttribute('width', String(spacing));
        pattern.setAttribute('height', String(spacing));
        pattern.setAttribute('patternTransform', `rotate(${angle})`);
        const addLine = (x1, y1, x2, y2) => {
          const line = document.createElementNS(svgNamespace, 'line');
          line.setAttribute('x1', String(x1));
          line.setAttribute('y1', String(y1));
          line.setAttribute('x2', String(x2));
          line.setAttribute('y2', String(y2));
          line.setAttribute('stroke', colour);
          line.setAttribute('stroke-width', String(width));
          line.setAttribute('stroke-linecap', style.line_cap || 'square');
          if (dashArray) line.setAttribute('stroke-dasharray', dashArray);
          pattern.append(line);
        };
        addLine(spacing / 2, 0, spacing / 2, spacing);
        if (style.pattern_crosshatch) addLine(0, spacing / 2, spacing, spacing / 2);
        defs.append(pattern);
      }
      return `url(#${id})`;
    };
    const qgisLinePatternFill = style => qgisLinePatternFillFor(riparianDefs, 'rfi-qgis-line-pattern', style);
    const qgisDisplayLinePatternFill = style => qgisLinePatternFillFor(riparianDisplayDefs, 'rfi-qgis-display-line-pattern', style);
    const landusePatternFill = symbol => {
      if (symbol.pattern === 'solid') return symbol.color;
      const id = `rfi-landuse-${symbol.pattern}-${symbol.color.slice(1)}`;
      if (!landuseDefs.querySelector(`#${id}`)) {
        const pattern = document.createElementNS(svgNamespace, 'pattern');
        pattern.setAttribute('id', id); pattern.setAttribute('patternUnits', 'userSpaceOnUse'); pattern.setAttribute('width', '8'); pattern.setAttribute('height', '8');
        const background = document.createElementNS(svgNamespace, 'rect'); background.setAttribute('width', '8'); background.setAttribute('height', '8'); background.setAttribute('fill', symbol.color); pattern.append(background);
        const ink = 'rgba(20, 38, 26, .72)';
        if (symbol.pattern === 'dots') {
          const dot = document.createElementNS(svgNamespace, 'circle'); dot.setAttribute('cx', '2'); dot.setAttribute('cy', '2'); dot.setAttribute('r', '1'); dot.setAttribute('fill', ink); pattern.append(dot);
        } else {
          const hatch = document.createElementNS(svgNamespace, 'path');
          hatch.setAttribute('d', symbol.pattern === 'crosshatch' ? 'M-2,2 L2,-2 M0,8 L8,0 M6,10 L10,6 M6,-2 L10,2 M0,0 L8,8 M-2,6 L2,10' : 'M-2,2 L2,-2 M0,8 L8,0 M6,10 L10,6');
          hatch.setAttribute('stroke', ink); hatch.setAttribute('stroke-width', '1'); pattern.append(hatch);
        }
        landuseDefs.append(pattern);
      }
      return `url(#${id})`;
    };
    L.control.scale({position: 'bottomleft', imperial: true}).addTo(map);
    const compass = L.control({position: 'bottomleft'});
    compass.onAdd = () => {
      const control = L.DomUtil.create('div', 'rfi-rotate-control');
      control.setAttribute('role', 'group'); control.setAttribute('aria-label', 'Map rotation compass');
      control.innerHTML = '<button type="button" class="rfi-rotate-control__direction rfi-rotate-control__north" data-bearing="0" aria-label="Orient map north-up">N</button><button type="button" class="rfi-rotate-control__direction rfi-rotate-control__east" data-bearing="270" aria-label="Orient map east-up">E</button><button type="button" class="rfi-rotate-control__direction rfi-rotate-control__south" data-bearing="180" aria-label="Orient map south-up">S</button><button type="button" class="rfi-rotate-control__direction rfi-rotate-control__west" data-bearing="90" aria-label="Orient map west-up">W</button><button type="button" class="rfi-rotate-control__reset" aria-label="Drag to rotate the map; click to reset north"><svg class="rfi-rotate-control__needle" viewBox="0 0 34 72" aria-hidden="true" focusable="false"><path class="rfi-rotate-control__needle-body" fill-rule="evenodd" d="M17 1 30 36 17 71 4 36Z M17 10 10 33 24 33Z"/></svg></button>';
      L.DomEvent.disableClickPropagation(control); L.DomEvent.disableScrollPropagation(control);
      const needle = control.querySelector('.rfi-rotate-control__needle');
      const reset = control.querySelector('.rfi-rotate-control__reset');
      const updateCompass = () => {
        const bearing = map.getBearing ? map.getBearing() : 0;
        needle.style.transform = `rotate(${bearing}deg)`;
        reset.setAttribute('aria-label', Math.abs(bearing) < .5 ? 'Map is north-up; drag compass to rotate' : `Drag compass to rotate; click to reset north (currently ${Math.round(bearing)} degrees)`);
      };
      control.querySelectorAll('[data-bearing]').forEach(button => button.addEventListener('click', () => map.setBearing(Number(button.dataset.bearing))));
      let dragStartAngle = 0, dragStartBearing = 0, dragged = false, suppressReset = false;
      const compassAngle = event => {
        const bounds = control.getBoundingClientRect();
        return Math.atan2(event.clientY - (bounds.top + bounds.height / 2), event.clientX - (bounds.left + bounds.width / 2)) * 180 / Math.PI;
      };
      const stopDrag = () => {
        document.removeEventListener('pointermove', dragCompass);
        document.removeEventListener('pointerup', stopDrag);
        document.removeEventListener('pointercancel', stopDrag);
        if (dragged) {
          suppressReset = true; control.classList.remove('is-rotating');
          setTimeout(() => { suppressReset = false; }, 0);
        } else map.setBearing(0);
      };
      const dragCompass = event => {
        const delta = compassAngle(event) - dragStartAngle;
        if (Math.abs(delta) > 1) { dragged = true; control.classList.add('is-rotating'); map.setBearing(dragStartBearing + delta); }
      };
      reset.addEventListener('pointerdown', event => {
        event.preventDefault(); dragStartAngle = compassAngle(event); dragStartBearing = map.getBearing(); dragged = false;
        document.addEventListener('pointermove', dragCompass); document.addEventListener('pointerup', stopDrag); document.addEventListener('pointercancel', stopDrag);
      });
      reset.addEventListener('click', () => { if (suppressReset) { suppressReset = false; return; } map.setBearing(0); });
      map.on('rotate', updateCompass); updateCompass();
      return control;
    };
    compass.addTo(map);
    let config;
    try { config = await fetch(configUrl).then(r => { if (!r.ok) throw Error(r.status); return r.json(); }); }
    catch (error) {
      panel.textContent = 'Map configuration could not be loaded.';
      status.textContent = 'Map data unavailable.';
      loading?.remove();
      root.classList.add('rfi-map--error');
      console.error('Could not load map manifest.', error);
      return;
    }
    const configuredBasemaps = Array.isArray(config.basemaps) ? config.basemaps : [];
    const baseLayers = {};
    configuredBasemaps.forEach((basemap, index) => {
      if (basemap?.type !== 'xyz' || !basemap.url) return;
      const tile = L.tileLayer(resolveTileUrl(basemap.url), {
        maxZoom: basemap.max_zoom || 19,
        attribution: basemap.attribution || '',
        crossOrigin: true,
        referrerPolicy: 'no-referrer',
        keepBuffer: 4,
      });
      baseLayers[basemap.name || `Basemap ${index + 1}`] = tile;
      if (basemap.locked || basemap.visible || (!index && !configuredBasemaps.some(entry => entry.visible))) tile.addTo(map);
    });
    if (Object.keys(baseLayers).length > 1) L.control.layers(baseLayers, {}, {position: 'bottomright'}).addTo(map);
    if (!Object.keys(baseLayers).length) root.classList.add('rfi-map--blank');
    status.textContent = config.mode === 'symbology'
      ? (Object.keys(baseLayers).length
        ? `${config.title || 'Basemap only'} · no project data loaded`
        : 'Blank canvas · no data loaded')
      : (config.title ? `${config.title} · data loaded` : 'Map data loaded');
    renderLegends();
    const extent = L.featureGroup();
    let focusLayer;
    let selectedMonkeyTransect;
    const clearMonkeyTransectSelection = () => {
      selectedMonkeyTransect?.getElement?.()?.classList.remove('rfi-monkey-transect--selected');
      selectedMonkeyTransect = undefined;
    };
    map.on('click', clearMonkeyTransectSelection);
    (config.layers || []).filter(layer => layer.type === 'xyz').forEach(layer => {
      const tile = L.tileLayer(resolveTileUrl(layer.url), {opacity: layer.opacity || .7, attribution: layer.attribution || ''});
      if (layer.visible) { tile.addTo(map); }
      const label = document.createElement('label');
      const input = document.createElement('input'); input.type = 'checkbox'; input.checked = !!layer.visible;
      label.append(input, document.createTextNode(' ' + layer.name)); placeLayerControl(label, layer.group, false, layer);
      input.addEventListener('change', e => e.target.checked ? tile.addTo(map) : map.removeLayer(tile));
    });
    for (const layer of (config.layers || []).filter(layer => layer.type === 'geojson')) {
      const locked = layer.locked === true;
      const initiallyVisible = locked || !!layer.visible;
      let label, input;
      if (!locked) {
        label = document.createElement('label');
        input = document.createElement('input'); input.type = 'checkbox'; input.checked = initiallyVisible;
        label.append(input, document.createTextNode(' ' + layer.name)); placeLayerControl(label, layer.group, !!layer.primary_boundary, layer);
      }
      if (!layer.url) {
        if (label) { label.classList.add('rfi-muted'); label.title = 'No public URL configured for this data source.'; }
        continue;
      }
      try {
        const data = await fetch(resolveUrl(layer.url)).then(r => r.json());
        if (Array.isArray(data.features)) {
          data.features.forEach((feature, index) => {
            feature.properties = feature.properties || {};
            feature.properties._rfi_feature_index = index + 1;
          });
        }
        const passivePatternOverlay = layer.style?.kind === 'qgis-line-pattern-fill' && layer.interactive === false;
        const vectorRenderer = layer.style?.kind === 'landuse-parcels'
          ? landuseRenderer
          : layer.style?.kind === 'qgis-line-pattern-fill'
            ? passivePatternOverlay ? riparianDisplayRenderer : riparianRenderer
            : undefined;
        const vectorPatternFill = layer.style?.kind === 'landuse-parcels'
          ? landusePatternFill
          : layer.style?.kind === 'qgis-line-pattern-fill'
            ? passivePatternOverlay ? qgisDisplayLinePatternFill : qgisLinePatternFill
            : undefined;
        const geojson = layer.style?.kind === 'monkey-heatmap'
          ? createMonkeyHeatLayer(data, layer.style)
          : L.geoJSON(data, {renderer: vectorRenderer, interactive: layer.interactive !== false, style: feature => vectorStyle(layer, feature, vectorPatternFill), onEachFeature: (f, l) => {
          if (layer.style?.kind === 'monkey-transects') {
            const transectName = propertyValue(f.properties, ['title', 'Transect']) || 'Study transect';
            l.bindTooltip(escapeHtml(`Transect ${transectName}`), {sticky: true, direction: 'top'});
            l.on('click', event => {
              if (event.originalEvent) L.DomEvent.stopPropagation(event.originalEvent);
              clearMonkeyTransectSelection();
              selectedMonkeyTransect = l;
              l.getElement()?.classList.add('rfi-monkey-transect--selected');
            });
            l.on('remove', () => {
              if (selectedMonkeyTransect === l) selectedMonkeyTransect = undefined;
            });
          }
          if (layer.style?.kind === 'monkey-sightings') {
            const entry = propertyValue(f.properties, ['Entry', 'ObjectId']) || '—';
            const transect = propertyValue(f.properties, ['Transect']) || '—';
            const groupSize = propertyValue(f.properties, ['Group_Size', 'Group size']) || '—';
            l.bindTooltip(escapeHtml(`Sighting ${entry} · ${transect} · group size ${groupSize}`), {sticky: true, direction: 'top'});
          }
          const isParcel = layer.interactive !== false && ['qgis-polygon', 'qgis-line-pattern-fill', 'landuse', 'landuse-parcels'].includes(layer.style?.kind) && /Polygon$/.test(f.geometry?.type || '');
          if (isParcel) {
            l.bindPopup(buildParcelPopup(layer, f, resolveUrl), {
              className: 'rfi-parcel-popup-shell',
              maxWidth: 700,
              minWidth: 300,
              maxHeight: 590,
              autoPan: false,
              autoPanPaddingTopLeft: [24, 92],
              autoPanPaddingBottomRight: [24, 96],
            });
          }
        }});
        const riparianDisplay = layer.style?.kind === 'qgis-line-pattern-fill' && !passivePatternOverlay
          ? L.geoJSON(data, {
              renderer: riparianDisplayRenderer,
              interactive: false,
              style: feature => ({
                ...vectorStyle(layer, feature, qgisDisplayLinePatternFill),
                className: `rfi-riparian-display-feature ${layerClassFor(layer)}`,
              }),
            })
          : null;
        extent.addLayer(geojson);
        if (initiallyVisible) {
          geojson.addTo(map);
          riparianDisplay?.addTo(map);
        }
        registerLanduseLegend(layer);
        renderLanduseLegend();
        if (layer.zoom_on_load || layer.id === 'laf-border-web') focusLayer = geojson;
        if (layer.legend && initiallyVisible) { activeLegends.set(legendKey(layer), layer.legend); renderLegends(); }
        if (input) {
          input.addEventListener('change', e => {
            if (e.target.checked) {
              geojson.addTo(map);
              riparianDisplay?.addTo(map);
              if (layer.legend) activeLegends.set(legendKey(layer), layer.legend);
            }
            else {
              map.removeLayer(geojson);
              if (riparianDisplay) map.removeLayer(riparianDisplay);
              activeLegends.delete(legendKey(layer));
            }
            renderLegends();
          });
        }
      } catch (error) {
        console.error(`Could not load layer: ${layer.name}`, error);
        if (label) { label.classList.add('rfi-muted'); label.title = 'Layer could not be fetched; see the browser console for details.'; }
      }
    }
    for (const asset of (config.satellite_assets || [])) {
      if (asset.kind === 'timeline-health-overlay') continue;
      // Source GeoTIFFs without a public URL are retained in the manifest but
      // are not useful rows in the browser UI. Generated health PNGs remain.
      if (!asset.displayable_overlay && !asset.url) continue;
      const row = document.createElement('div'); row.className = 'rfi-asset';
      row.innerHTML = `<b>${escapeHtml(asset.name)}</b><small>${escapeHtml(asset.kind)} · ${escapeHtml(asset.format.toUpperCase())}</small>`;
      if (asset.url) { const a = document.createElement('a'); a.href = resolveUrl(asset.url); a.target = '_blank'; a.rel = 'noopener'; a.textContent = asset.displayable_overlay ? 'Open overlay' : 'Open data'; row.append(a); }
      assetsPanel.append(row);
      if (asset.displayable_overlay && asset.url && asset.bounds) {
        const overlay = L.imageOverlay(resolveUrl(asset.url), asset.bounds, {opacity: asset.opacity ?? .65});
        const control = document.createElement('label'); control.innerHTML = `<input type="checkbox"> ${escapeHtml(asset.name)} overlay`; placeLayerControl(control, asset.group, false, asset);
        const input = control.querySelector('input');
        input.addEventListener('change', e => {
          if (e.target.checked) { overlay.addTo(map); if (asset.legend) activeLegends.set(legendKey(asset), asset.legend); }
          else { map.removeLayer(overlay); activeLegends.delete(legendKey(asset)); }
          renderLegends();
        });
      }
    }
    const healthConfig = config.environmental_health;
    const healthAnalyses = Array.isArray(healthConfig?.analyses)
      ? healthConfig.analyses.filter(analysis => analysis.metric && analysis.timeline_url && analysis.legend)
      : [];
    const healthYears = Array.isArray(healthConfig?.years)
      ? healthConfig.years.map(Number).filter(Number.isFinite).sort((a, b) => a - b)
      : [];
    if (healthAnalyses.length && healthYears.length && Array.isArray(healthConfig.bounds)) {
      const control = document.createElement('section');
      control.className = 'rfi-timeline'; control.hidden = true;
      control.setAttribute('aria-label', 'Environmental health analysis controls');
      control.innerHTML = `<b>Environmental health analysis</b><label>Analysis <select aria-label="Environmental analysis"></select></label><p class="rfi-timeline__description" aria-live="polite"></p><label>Year <output>${healthYears.at(-1)}</output><input type="range" min="0" max="${healthYears.length - 1}" value="${healthYears.length - 1}" step="1" aria-label="Analysis year"></label>`;
      root.append(control);
      L.DomEvent.disableClickPropagation(control); L.DomEvent.disableScrollPropagation(control);
      const metricSelect = control.querySelector('select');
      const analysisDescription = control.querySelector('.rfi-timeline__description');
      const periodSlider = control.querySelector('input[type="range"]');
      const periodOutput = control.querySelector('output');
      metricSelect.replaceChildren(...healthAnalyses.map(analysis => {
        const option = document.createElement('option'); option.value = analysis.metric; option.textContent = analysis.name; return option;
      }));
      metricSelect.value = healthAnalyses.find(analysis => analysis.metric === 'NDVI')?.metric || healthAnalyses[0].metric;
      let healthOverlay, activeHealthLegendKey;
      const clearHealthOverlay = () => {
        if (healthOverlay) map.removeLayer(healthOverlay);
        if (activeHealthLegendKey) activeLegends.delete(activeHealthLegendKey);
        healthOverlay = undefined; activeHealthLegendKey = undefined;
      };
      const updateHealthOverlay = () => {
        clearHealthOverlay();
        const analysis = healthAnalyses.find(item => item.metric === metricSelect.value) || healthAnalyses[0];
        analysisDescription.textContent = analysis.legend.description || `${analysis.name} analysis.`;
        const periodIndex = Number(periodSlider.value);
        const year = healthYears[periodIndex];
        const periodLabel = String(year);
        periodOutput.value = periodLabel; periodOutput.textContent = periodLabel;
        control.dataset.analysis = analysis.metric;
        control.dataset.period = periodLabel;
        if (activeSection !== 'environmental-health-analysis') { renderLegends(); return; }
        const imageUrl = analysis.timeline_url.replace('{year}', String(year));
        healthOverlay = L.imageOverlay(resolveUrl(imageUrl), healthConfig.bounds, {
          opacity: healthConfig.opacity ?? .72,
          className: 'rfi-health-overlay',
          alt: `${analysis.name}, ${periodLabel}`,
        });
        healthOverlay.on('error', () => console.error(`Could not load environmental analysis: ${analysis.name}, ${periodLabel}`));
        healthOverlay.addTo(map);
        activeHealthLegendKey = analysis.metric;
        activeLegends.set(activeHealthLegendKey, analysis.legend);
        if (focusLayer?.bringToFront) focusLayer.bringToFront();
        renderLegends();
      };
      metricSelect.addEventListener('change', updateHealthOverlay);
      periodSlider.addEventListener('input', updateHealthOverlay);
      root.addEventListener('rfi-section-change', updateHealthOverlay);
      environmentalAnalysisControl = control;
      environmentalAnalysisCount = healthAnalyses.length;
      updateSectionVisibility();
    }
    if (focusLayer && focusLayer.getBounds().isValid()) {
      farmBoundaryBounds = focusLayer.getBounds();
      homeBounds = farmBoundaryBounds.pad(.12);
      if (focusLayer.bringToFront) focusLayer.bringToFront();
      console.info('Map focused on the configured opening boundary.');
    } else if (extent.getLayers().length) {
      farmBoundaryBounds = extent.getBounds();
      homeBounds = farmBoundaryBounds.pad(.08);
      console.warn('LAF_border_web was not loaded; map focused on all layers instead.');
    }
    // In-app and embedded browsers can initialize a background tab before its
    // map container has its final dimensions. Recheck the size over the first
    // few frames so the configured boundary is reliably used as the opening
    // view without affecting later user navigation.
    fitHomeBounds();
    requestAnimationFrame(() => requestAnimationFrame(fitHomeBounds));
    setTimeout(fitHomeBounds, 300);
    if (document.hidden) {
      const fitWhenVisible = () => {
        if (document.hidden) return;
        fitHomeBounds();
        document.removeEventListener('visibilitychange', fitWhenVisible);
      };
      document.addEventListener('visibilitychange', fitWhenVisible);
    }
    emptyMessage = config.mode === 'symbology' ? 'No map data is connected.' : 'No web-ready QGIS layers were found.';
    loading?.remove();
    root.classList.add('rfi-map--ready');
    updateSectionVisibility();
  };
  const bootAll = () => document.querySelectorAll('.rfi-map').forEach(root => boot(root));
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bootAll);
  else bootAll();
})();
